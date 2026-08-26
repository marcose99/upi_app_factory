from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from pathlib import Path
from typing import Any

import pytest

from factory.documentation import (
    build_portal,
    canonical_json,
    canonical_sha256,
    validate_portal_integrity,
    write_document_pair,
)
from factory.governance_evolution import (
    AuthorityDecision,
    AuthorityDecisionAction,
    AuthorityRegistry,
    GovernanceControlPlane,
    GovernanceProposal,
    GovernanceSnapshot,
    GovernanceUpdateCenter,
    GovernanceValidation,
    ProposalOrigin,
    SourceAuthorityContract,
    SourceMetadata,
    SourceObservation,
    SourceVerification,
    UpdateCenterError,
    diff_governance_snapshots,
    project_impact,
    render_update_center_html,
    sha256_bytes,
    validate_update_center_document,
    write_update_center_pair,
)


DECISION_AUTHORITY = "AUTHORITY-governance-board"
SOURCE_CONTENT = {
    "SOURCE-policy": b'{"policy":"governed"}',
    "SOURCE-schema": b'{"schema":"governed"}',
}


def registry(*, reverse: bool = False) -> AuthorityRegistry:
    source_ids = list(SOURCE_CONTENT)
    if reverse:
        source_ids.reverse()
    return AuthorityRegistry(
        tuple(
            SourceAuthorityContract(
                authority_id=f"AUTHORITY-{source_id.lower()}",
                source_id=source_id,
                revision="revision:1",
                content_sha256=sha256_bytes(SOURCE_CONTENT[source_id]),
                source_type="SIGNED_GOVERNANCE_INPUT",
            )
            for source_id in source_ids
        )
    )


def verifications(
    authority_registry: AuthorityRegistry, *, reverse: bool = False
) -> tuple[SourceVerification, ...]:
    source_ids = list(SOURCE_CONTENT)
    if reverse:
        source_ids.reverse()
    observed = tuple(
        SourceObservation(
            SOURCE_CONTENT[source_id],
            SourceMetadata(
                authority_id=f"AUTHORITY-{source_id.lower()}",
                source_id=source_id,
                revision="revision:1",
                content_sha256=sha256_bytes(SOURCE_CONTENT[source_id]),
                source_type="SIGNED_GOVERNANCE_INPUT",
            ),
        )
        for source_id in source_ids
    )
    return authority_registry.verify_many(observed)


def snapshot(
    authority_registry: AuthorityRegistry,
    version: str,
    limit: int,
    *,
    predecessor: GovernanceSnapshot | None = None,
    reverse: bool = False,
) -> GovernanceSnapshot:
    bindings = tuple(
        authority_registry.contract_for(source_id).to_source_binding()
        for source_id in (
            ("SOURCE-schema", "SOURCE-policy") if reverse else ("SOURCE-policy", "SOURCE-schema")
        )
    )
    predecessor_id = predecessor.snapshot_id if predecessor is not None else None
    facts = {
        "FACT-z": {"value": "unchanged"},
        "FACT-limit": {"value": limit},
    }
    if reverse:
        facts = dict(reversed(tuple(facts.items())))
    payload: dict[str, Any] = {
        "rules": {"RULE-limit": {"effect": "DENY_ABOVE_LIMIT"}},
        "facts": facts,
    }
    if reverse:
        payload = dict(reversed(tuple(payload.items())))
    return GovernanceSnapshot(
        version_id=version,
        payload=payload,
        source_bindings=bindings,
        previous_snapshot_id=predecessor_id,
        supersedes_snapshot_id=predecessor_id,
    )


def qualify(
    plane: GovernanceControlPlane,
    authority_registry: AuthorityRegistry,
    governed: GovernanceSnapshot,
    sequence: int,
) -> tuple[GovernanceProposal, GovernanceValidation]:
    plane.observe_snapshot(governed)
    plane.verify_snapshot(governed.snapshot_id, verifications(authority_registry))
    proposal = GovernanceProposal(
        proposal_id=f"PROPOSAL-{sequence}",
        target_snapshot_id=governed.snapshot_id,
        evidence_identity=f"PROPOSAL-EVIDENCE-{sequence}",
        proposer_identity="MODEL-non-authoritative",
        origin=ProposalOrigin.AI,
    )
    plane.propose_snapshot(governed.snapshot_id, proposal)
    validation = GovernanceValidation(
        validation_id=f"VALIDATION-{sequence}",
        target_snapshot_id=governed.snapshot_id,
        proposal_id=proposal.proposal_id,
        evidence_identity=f"VALIDATION-EVIDENCE-{sequence}",
        validator_identity="TOOL-deterministic-qualification-v1",
        passed=True,
    )
    plane.validate_snapshot(governed.snapshot_id, validation)
    return proposal, validation


def promote(
    plane: GovernanceControlPlane,
    governed: GovernanceSnapshot,
    proposal: GovernanceProposal,
    validation: GovernanceValidation,
    sequence: int,
) -> None:
    plane.promote_snapshot(
        governed.snapshot_id,
        AuthorityDecision(
            decision_id=f"AUTHORITY-DECISION-{sequence}",
            authority_id=DECISION_AUTHORITY,
            action=AuthorityDecisionAction.PROMOTE,
            target_snapshot_id=governed.snapshot_id,
            evidence_identity=f"AUTHORITY-DECISION-EVIDENCE-{sequence}",
            expected_active_snapshot_id=plane.expected_active_snapshot_id,
            proposal_id=proposal.proposal_id,
            validation_id=validation.validation_id,
        ),
    )


def update_state(
    *, reverse: bool = False, candidate_version: str = "policy:2"
) -> tuple[
    GovernanceControlPlane,
    AuthorityRegistry,
    GovernanceSnapshot,
    GovernanceSnapshot,
]:
    authority_registry = registry(reverse=reverse)
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    active = snapshot(authority_registry, "policy:1", 10, reverse=reverse)
    proposed, validation = qualify(plane, authority_registry, active, 1)
    promote(plane, active, proposed, validation, 1)
    plane.start_execution(
        "EXECUTION-pinned-before-update",
        factory_source_identity="git:factory-commit-abc",
        requirement_identity="requirements:sha256-abc",
        evidence_snapshot_identity="evidence:sha256-def",
        tool_config_identity="tool-config:sha256-ghi",
    )
    candidate = snapshot(
        authority_registry,
        candidate_version,
        20,
        predecessor=active,
        reverse=reverse,
    )
    qualify(plane, authority_registry, candidate, 2)
    return plane, authority_registry, active, candidate


def center(
    *, reverse: bool = False, candidate_version: str = "policy:2"
) -> tuple[GovernanceUpdateCenter, GovernanceControlPlane]:
    plane, authority_registry, _active, candidate = update_state(
        reverse=reverse, candidate_version=candidate_version
    )
    return (
        GovernanceUpdateCenter(
            plane,
            candidate.snapshot_id,
            source_verifications=verifications(authority_registry, reverse=not reverse),
        ),
        plane,
    )


def reseal(document: dict[str, Any]) -> str:
    identity = dict(document)
    identity.pop("update_center_id", None)
    identity.pop("update_center_sha256", None)
    digest = canonical_sha256(identity)
    document["update_center_sha256"] = digest
    document["update_center_id"] = f"GOVERNANCE-UPDATE-CENTER-{digest}"
    return canonical_json(document)


def test_canonical_model_projects_required_evidence_and_decision_required_state() -> None:
    update_center, _plane = center()
    projected = update_center.to_dict()

    assert projected["active_snapshot"]["lifecycle_state"] == "ACTIVE"
    assert projected["observed_candidate"]["lifecycle_state"] == "VALIDATED"
    assert projected["verified_provenance"]["status"] == "AUTHORITY_VERIFIED"
    assert projected["freshness"]["overall_status"] == "CURRENT"
    assert projected["semantic_diff"]["changed"][0]["entity_id"] == "FACT-limit"
    assert projected["impact"]["has_unknown_impact"] is True
    assert projected["qualification_state"]["state"] == "PASSED"
    assert projected["qualification_state"]["proposal"]["origin"] == ("AI_NON_AUTHORITATIVE")
    assert projected["qualification_state"]["proposal_confers_authority"] is False
    assert projected["authority_decision_status"]["status"] == "DECISION_REQUIRED"
    assert projected["authority_decision_status"]["decision_record"] is None
    assert (
        projected["authority_decision_status"]["explicit_governed_authority_decision_required"]
        is True
    )
    assert projected["authority_decision_status"]["ui_can_create_authority"] is False
    assert all(value == "NOT_ASSERTED" for value in projected["assurance_boundaries"].values())
    assert update_center.to_json() == canonical_json(projected)
    assert update_center.update_center_sha256 == canonical_sha256(update_center.identity_payload())


def test_same_logical_view_is_stable_across_input_order() -> None:
    first, _first_plane = center(reverse=False)
    second, _second_plane = center(reverse=True)

    assert first.observed_candidate.snapshot_id == second.observed_candidate.snapshot_id
    assert first.to_json() == second.to_json()
    assert first.update_center_sha256 == second.update_center_sha256
    assert [
        item["source_id"] for item in first.to_dict()["verified_provenance"]["source_bindings"]
    ] == ["SOURCE-policy", "SOURCE-schema"]


def test_html_is_accessible_escaped_and_has_exact_json_parity() -> None:
    update_center, _plane = center(candidate_version='policy:<script>alert("unsafe")</script>')
    encoded = update_center.to_json()
    rendered = render_update_center_html(encoded)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    assert rendered.startswith('<!doctype html>\n<html lang="en">')
    assert f'name="json-sha256" content="{digest}"' in rendered
    assert rendered.count(digest) >= 3
    assert '<script>alert("unsafe")</script>' not in rendered
    assert "&lt;script&gt;alert" in rendered
    assert '<a href="#main">Skip to evidence</a>' in rendered
    assert 'aria-labelledby="authority-heading"' in rendered
    assert 'disabled aria-disabled="true"' in rendered
    assert "<form" not in rendered and "<script" not in rendered
    match = re.search(r'<pre id="canonical-json">(.*?)</pre>', rendered, re.DOTALL)
    assert match is not None
    assert html_module.unescape(match.group(1)) == encoded


def test_html_rejects_noncanonical_tampered_and_broken_reference_json() -> None:
    update_center, _plane = center()
    projected = update_center.to_dict()

    with pytest.raises(UpdateCenterError, match="exact canonical JSON"):
        render_update_center_html(json.dumps(projected, indent=2))

    tampered = update_center.to_dict()
    tampered["freshness"]["overall_status"] = "STALE"
    with pytest.raises(UpdateCenterError, match="digest mismatch"):
        render_update_center_html(canonical_json(tampered))

    broken = update_center.to_dict()
    broken["semantic_diff"]["after_snapshot_id"] = "GOVERNANCE-SNAPSHOT-missing"
    with pytest.raises(UpdateCenterError, match="broken candidate snapshot reference"):
        render_update_center_html(reseal(broken))


def test_unsupported_assurance_and_limitation_claims_fail_closed() -> None:
    update_center, _plane = center()
    unsupported = update_center.to_dict()
    unsupported["assurance_boundaries"]["certification"] = "CERTIFIED"
    with pytest.raises(UpdateCenterError, match="unsupported assurance claim"):
        render_update_center_html(reseal(unsupported))

    invented = update_center.to_dict()
    invented["limitations"][0]["description"] = "Externally approved."
    with pytest.raises(UpdateCenterError, match="unsupported or altered limitation"):
        validate_update_center_document(json.loads(reseal(invented)))


def test_projection_cannot_mutate_control_plane_or_captured_nested_state() -> None:
    update_center, plane = center()
    pin_before = plane.execution_pins[0].to_dict()
    transitions_before = plane.transition_history
    plane_digest_before = plane.control_plane_sha256

    render_update_center_html(update_center.to_json())

    assert plane.execution_pins[0].to_dict() == pin_before
    assert plane.transition_history == transitions_before
    assert plane.control_plane_sha256 == plane_digest_before
    with pytest.raises(TypeError, match="immutable"):
        update_center.execution_pinning["ui_mutation_supported"] = True  # type: ignore[index]
    with pytest.raises(TypeError, match="immutable"):
        update_center.limitations[0]["description"] = "mutated"  # type: ignore[index]


def test_stale_observation_remains_unverified_and_explicitly_stale() -> None:
    plane, authority_registry, active, _candidate = update_state()
    observed = snapshot(
        authority_registry,
        "policy:observed-stale",
        30,
        predecessor=active,
    )
    plane.observe_snapshot(observed)
    changed = b'{"policy":"changed"}'
    stale = authority_registry.verify(
        SourceObservation(
            changed,
            SourceMetadata(
                authority_id="AUTHORITY-source-policy",
                source_id="SOURCE-policy",
                revision="revision:2",
                content_sha256=sha256_bytes(changed),
                source_type="SIGNED_GOVERNANCE_INPUT",
            ),
        )
    )

    update_center = GovernanceUpdateCenter(
        plane, observed.snapshot_id, source_verifications=(stale,)
    )
    projected = update_center.to_dict()

    assert projected["observed_candidate"]["lifecycle_state"] == "OBSERVED_UNVERIFIED"
    assert projected["verified_provenance"]["status"] == "NOT_AUTHORITY_VERIFIED"
    assert projected["freshness"]["overall_status"] == "STALE"
    assert projected["qualification_state"]["state"] == "NOT_PROPOSED"
    assert projected["authority_decision_status"]["status"] == "NOT_READY"
    assert "LIMITATION-PROVENANCE" in {item["limitation_id"] for item in projected["limitations"]}


def test_current_verification_evidence_is_not_control_plane_activation() -> None:
    plane, authority_registry, active, _candidate = update_state()
    observed = snapshot(
        authority_registry,
        "policy:observed-current",
        40,
        predecessor=active,
    )
    plane.observe_snapshot(observed)
    history_before = plane.transition_history

    update_center = GovernanceUpdateCenter(
        plane,
        observed.snapshot_id,
        source_verifications=verifications(authority_registry),
    )
    projected = update_center.to_dict()

    assert projected["freshness"]["overall_status"] == "CURRENT"
    assert projected["verified_provenance"]["status"] == "NOT_AUTHORITY_VERIFIED"
    assert projected["observed_candidate"]["lifecycle_state"] == "OBSERVED_UNVERIFIED"
    assert projected["authority_decision_status"]["status"] == "NOT_READY"
    assert plane.transition_history == history_before
    assert plane.active_snapshot is active


def test_cross_artifact_references_fail_closed_before_rendering() -> None:
    plane, authority_registry, active, candidate = update_state()
    unrelated = snapshot(authority_registry, "policy:unrelated", 99, predecessor=active)
    plane.observe_snapshot(unrelated)

    wrong_diff = diff_governance_snapshots(active, unrelated)
    with pytest.raises(UpdateCenterError, match="semantic diff references"):
        GovernanceUpdateCenter(
            plane,
            candidate.snapshot_id,
            semantic_diff=wrong_diff,
        )

    right_diff = diff_governance_snapshots(active, candidate)
    wrong_impact = project_impact(wrong_diff)
    with pytest.raises(UpdateCenterError, match="different semantic diff"):
        GovernanceUpdateCenter(
            plane,
            candidate.snapshot_id,
            semantic_diff=right_diff,
            impact_projection=wrong_impact,
        )


def test_portal_pair_uses_relative_paths_and_passes_documentation_integrity_gate(
    tmp_path: Path,
) -> None:
    update_center, _plane = center()
    entry = write_update_center_pair(tmp_path, "governance/update_center", update_center)
    portal = build_portal("upi_app_factory", (entry,))
    write_document_pair(tmp_path, "index", portal)

    assert entry["json_path"] == "governance/update_center.json"
    assert entry["html_path"] == "governance/update_center.html"
    assert tmp_path.as_posix() not in canonical_json(entry)
    assert entry["json_sha256"] == update_center.json_sha256
    assert validate_portal_integrity(portal, tmp_path)["status"] == "PROVEN"
    assert entry["json_sha256"] in (tmp_path / entry["html_path"]).read_text(encoding="utf-8")

    with pytest.raises(UpdateCenterError, match="safe relative path"):
        write_update_center_pair(tmp_path, "../outside", update_center)
    with pytest.raises(UpdateCenterError, match="safe relative path"):
        write_update_center_pair(tmp_path, "/absolute", update_center)
