from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from factory.documentation import canonical_json, canonical_sha256
from factory.governance_evolution import (
    AffectedExecutionPolicy,
    AuthorityDecision,
    AuthorityDecisionAction,
    AuthorityRegistry,
    EvidenceAuthorityRole,
    EvolutionLedger,
    EvolutionLedgerEntry,
    EvolutionLedgerError,
    ExecutionDisposition,
    ExecutionPin,
    GENESIS_LEDGER_ENTRY_ID,
    GovernedEvolutionRecord,
    GovernanceControlPlane,
    GovernanceProposal,
    GovernanceSnapshot,
    GovernanceValidation,
    IdentityAvailability,
    LedgerIntegrityError,
    MeasurementStatus,
    ProposalOrigin,
    ReproductionComponent,
    ReproductionIdentity,
    ReproductionRecord,
    SourceAuthorityContract,
    SourceMetadata,
    SourceObservation,
    diff_governance_snapshots,
    project_impact,
    sha256_bytes,
    validate_evolution_ledger_document,
)


POLICY_BYTES = b'{"governance":"ledger-fixture","revision":1}'
DECISION_AUTHORITY = "AUTHORITY-governance-board"


def registry() -> AuthorityRegistry:
    return AuthorityRegistry(
        (
            SourceAuthorityContract(
                authority_id="AUTHORITY-policy-owner",
                source_id="SOURCE-policy",
                revision="revision:1",
                content_sha256=sha256_bytes(POLICY_BYTES),
                source_type="SIGNED_POLICY_BUNDLE",
            ),
        )
    )


def source_evidence(
    authority_registry: AuthorityRegistry,
) -> tuple[SourceObservation, Any]:
    metadata = SourceMetadata(
        authority_id="AUTHORITY-policy-owner",
        source_id="SOURCE-policy",
        revision="revision:1",
        content_sha256=sha256_bytes(POLICY_BYTES),
        source_type="SIGNED_POLICY_BUNDLE",
    )
    observation = SourceObservation(POLICY_BYTES, metadata)
    return observation, authority_registry.verify(observation)


def snapshot(
    authority_registry: AuthorityRegistry,
    version: int,
    predecessor: GovernanceSnapshot | None = None,
) -> GovernanceSnapshot:
    predecessor_id = predecessor.snapshot_id if predecessor is not None else None
    return GovernanceSnapshot(
        version_id=f"policy:{version}",
        payload={
            "rules": {"RULE-limit": {"effect": "DENY_ABOVE_LIMIT"}},
            "facts": {"FACT-limit": {"value": version * 10}},
        },
        source_bindings=(
            authority_registry.contract_for("SOURCE-policy").to_source_binding(),
        ),
        previous_snapshot_id=predecessor_id,
        supersedes_snapshot_id=predecessor_id,
    )


def proposal(governed: GovernanceSnapshot, version: int) -> GovernanceProposal:
    return GovernanceProposal(
        proposal_id=f"PROPOSAL-{version}",
        target_snapshot_id=governed.snapshot_id,
        evidence_identity=f"PROPOSAL-EVIDENCE-{version}",
        proposer_identity="MODEL-observer" if version == 1 else "TOOL-semantic-diff-v1",
        origin=ProposalOrigin.AI if version == 1 else ProposalOrigin.DETERMINISTIC_TOOL,
    )


def validation(
    governed: GovernanceSnapshot,
    proposed: GovernanceProposal,
    version: int,
) -> GovernanceValidation:
    return GovernanceValidation(
        validation_id=f"VALIDATION-{version}",
        target_snapshot_id=governed.snapshot_id,
        proposal_id=proposed.proposal_id,
        evidence_identity=f"VALIDATION-EVIDENCE-{version}",
        validator_identity="TOOL-deterministic-qualification-v1",
        passed=True,
    )


def authority_decision(
    plane: GovernanceControlPlane,
    governed: GovernanceSnapshot,
    action: AuthorityDecisionAction,
    sequence: int,
    *,
    proposed: GovernanceProposal | None = None,
    qualified: GovernanceValidation | None = None,
    disposition: ExecutionDisposition | None = None,
) -> AuthorityDecision:
    return AuthorityDecision(
        decision_id=f"AUTHORITY-DECISION-{sequence}",
        authority_id=DECISION_AUTHORITY,
        action=action,
        target_snapshot_id=governed.snapshot_id,
        evidence_identity=f"AUTHORITY-EVIDENCE-{sequence}",
        expected_active_snapshot_id=plane.expected_active_snapshot_id,
        proposal_id=proposed.proposal_id if proposed is not None else None,
        validation_id=qualified.validation_id if qualified is not None else None,
        execution_disposition=disposition,
    )


def promote(
    plane: GovernanceControlPlane,
    authority_registry: AuthorityRegistry,
    governed: GovernanceSnapshot,
    version: int,
) -> tuple[
    SourceObservation,
    Any,
    GovernanceProposal,
    GovernanceValidation,
    AuthorityDecision,
    Any,
]:
    observation, verification = source_evidence(authority_registry)
    plane.observe_snapshot(governed)
    plane.verify_snapshot(governed.snapshot_id, verification)
    proposed = proposal(governed, version)
    plane.propose_snapshot(governed.snapshot_id, proposed)
    qualified = validation(governed, proposed, version)
    plane.validate_snapshot(governed.snapshot_id, qualified)
    decision = authority_decision(
        plane,
        governed,
        AuthorityDecisionAction.PROMOTE,
        version,
        proposed=proposed,
        qualified=qualified,
    )
    transition = plane.promote_snapshot(governed.snapshot_id, decision)
    return observation, verification, proposed, qualified, decision, transition


def execution_policy(
    decision: AuthorityDecision,
    governed: GovernanceSnapshot,
    *,
    status: MeasurementStatus = MeasurementStatus.MEASURED,
    classifications: tuple[Any, ...] = (),
) -> AffectedExecutionPolicy:
    return AffectedExecutionPolicy(
        target_snapshot_id=governed.snapshot_id,
        authority_decision_id=decision.decision_id,
        measurement_status=status,
        classifications=classifications,
    )


def start_execution(
    plane: GovernanceControlPlane, execution_id: str
) -> ExecutionPin:
    return plane.start_execution(
        execution_id,
        factory_source_identity="git:factory-commit-abc",
        requirement_identity="requirement:REQ-M2.5F",
        evidence_snapshot_identity="evidence:sha256-def",
        tool_config_identity="tool-config:sha256-ghi",
    )


def promotion_record(
    *,
    plane: GovernanceControlPlane,
    authority_registry: AuthorityRegistry,
    governed: GovernanceSnapshot,
    version: int,
    prior: GovernanceSnapshot | None,
) -> GovernedEvolutionRecord:
    observation, verification, proposed, qualified, decision, transition = promote(
        plane, authority_registry, governed, version
    )
    execution_pin = start_execution(plane, f"EXECUTION-{version}")
    semantic_diff = (
        diff_governance_snapshots(prior, governed) if prior is not None else None
    )
    impact = project_impact(semantic_diff) if semantic_diff is not None else None
    return GovernedEvolutionRecord(
        action=AuthorityDecisionAction.PROMOTE,
        change_reason_evidence_identity=decision.evidence_identity,
        source_observations=(observation,),
        source_verifications=(verification,),
        prior_snapshot=prior,
        semantic_diff=semantic_diff,
        impact_projection=impact,
        proposal=proposed,
        validation=qualified,
        authority_decision=decision,
        resulting_snapshot=governed,
        lifecycle_transition=transition,
        affected_execution_policy=execution_policy(decision, governed),
        reproduction=ReproductionRecord.from_execution_fingerprint(
            execution_pin.execution_fingerprint
        ),
    )


def two_promotion_scenario() -> tuple[
    EvolutionLedger,
    GovernanceControlPlane,
    GovernanceSnapshot,
    GovernanceSnapshot,
    GovernedEvolutionRecord,
    GovernedEvolutionRecord,
]:
    authority_registry = registry()
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    first = snapshot(authority_registry, 1)
    first_record = promotion_record(
        plane=plane,
        authority_registry=authority_registry,
        governed=first,
        version=1,
        prior=None,
    )
    second = snapshot(authority_registry, 2, first)
    second_record = promotion_record(
        plane=plane,
        authority_registry=authority_registry,
        governed=second,
        version=2,
        prior=first,
    )
    ledger = EvolutionLedger()
    ledger.append(first_record)
    ledger.append(second_record)
    return ledger, plane, first, second, first_record, second_record


def test_entries_bind_full_evolution_evidence_and_append_in_hash_order() -> None:
    ledger, _plane, first, second, first_record, second_record = two_promotion_scenario()

    assert [entry.sequence for entry in ledger.entries] == [1, 2]
    assert ledger.entries[0].previous_entry_id == GENESIS_LEDGER_ENTRY_ID
    assert ledger.entries[1].previous_entry_id == ledger.entries[0].entry_id
    assert ledger.verify_integrity()
    assert second_record.prior_snapshot is first
    assert second_record.semantic_diff is not None
    assert second_record.semantic_diff.before_snapshot_id == first.snapshot_id
    assert second_record.semantic_diff.after_snapshot_id == second.snapshot_id
    assert second_record.impact_projection is not None
    assert second_record.impact_projection.semantic_diff_id == (
        second_record.semantic_diff.diff_id
    )
    assert second_record.proposal is not None
    assert second_record.validation is not None
    assert second_record.authority_decision.target_snapshot_id == second.snapshot_id
    assert second_record.resulting_snapshot is second
    assert first_record.affected_execution_policy.measurement_status is (
        MeasurementStatus.MEASURED
    )
    assert ledger.to_json() == canonical_json(ledger.to_dict())
    assert ledger.ledger_sha256 == canonical_sha256(ledger.identity_payload())


def test_ai_proposal_observation_verified_fact_and_governed_authority_are_distinct() -> None:
    ledger, _plane, _first, _second, first_record, second_record = (
        two_promotion_scenario()
    )
    first_roles = {item.role for item in first_record.evidence_authority}
    second_roles = {item.role for item in second_record.evidence_authority}

    assert EvidenceAuthorityRole.OBSERVATION_NON_AUTHORITATIVE in first_roles
    assert EvidenceAuthorityRole.AI_PROPOSAL_NON_AUTHORITATIVE in first_roles
    assert EvidenceAuthorityRole.SOURCE_FACT_AUTHORITY_VERIFIED in first_roles
    assert EvidenceAuthorityRole.GOVERNED_AUTHORITY_DECISION in first_roles
    assert EvidenceAuthorityRole.TOOL_PROPOSAL_NON_AUTHORITATIVE in second_roles
    assert ledger.to_dict()["entries"][0]["record"]["proposal"]["origin"] == (
        "AI_NON_AUTHORITATIVE"
    )


def test_sealed_history_is_immutable_and_tampering_is_detected() -> None:
    ledger, _plane, _first, _second, first_record, _second_record = (
        two_promotion_scenario()
    )
    with pytest.raises(FrozenInstanceError):
        ledger.entries[0].previous_entry_id = "ALTERED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first_record.change_reason_evidence_identity = "ALTERED"  # type: ignore[misc]

    object.__setattr__(
        first_record.authority_decision,
        "evidence_identity",
        "AUTHORITY-EVIDENCE-tampered",
    )
    with pytest.raises(LedgerIntegrityError, match="record content"):
        ledger.verify_integrity()


def test_canonical_document_validator_detects_tampering_and_missing_predecessor() -> None:
    ledger, _plane, _first, _second, _first_record, _second_record = (
        two_promotion_scenario()
    )
    validated = validate_evolution_ledger_document(ledger.to_json())
    assert validated["ledger_id"] == ledger.ledger_id

    tampered = json.loads(ledger.to_json())
    tampered["entries"][0]["record"]["authority_decision"][
        "evidence_identity"
    ] = "AUTHORITY-EVIDENCE-tampered"
    with pytest.raises(LedgerIntegrityError, match="record content"):
        validate_evolution_ledger_document(tampered)

    missing_predecessor = json.loads(ledger.to_json())
    missing_predecessor["entries"][1]["previous_entry_id"] = (
        "GOVERNED-EVOLUTION-LEDGER-ENTRY-missing"
    )
    with pytest.raises(LedgerIntegrityError, match="predecessor"):
        validate_evolution_ledger_document(missing_predecessor)

    with pytest.raises(LedgerIntegrityError, match="exact canonical JSON"):
        validate_evolution_ledger_document(json.dumps(validated, indent=2))


def test_replay_rejects_out_of_order_and_missing_predecessor_entries() -> None:
    ledger, _plane, _first, _second, first_record, _second_record = (
        two_promotion_scenario()
    )

    with pytest.raises(LedgerIntegrityError, match="sequence"):
        EvolutionLedger.replay(reversed(ledger.entries))

    missing_predecessor = EvolutionLedgerEntry(
        sequence=1,
        previous_entry_id="GOVERNED-EVOLUTION-LEDGER-ENTRY-missing",
        record=first_record,
    )
    with pytest.raises(LedgerIntegrityError, match="predecessor"):
        EvolutionLedger.replay((missing_predecessor,))


def test_rollback_and_revocation_append_new_history_without_erasure() -> None:
    ledger, plane, first, second, first_record, _second_record = two_promotion_scenario()
    history_before = ledger.entries

    rollback_decision = authority_decision(
        plane, first, AuthorityDecisionAction.ROLLBACK, 3
    )
    rollback_transition = plane.rollback_to_snapshot(first.snapshot_id, rollback_decision)
    rollback_diff = diff_governance_snapshots(second, first)
    rollback_record = GovernedEvolutionRecord(
        action=AuthorityDecisionAction.ROLLBACK,
        change_reason_evidence_identity=rollback_decision.evidence_identity,
        source_observations=(),
        source_verifications=(),
        prior_snapshot=second,
        semantic_diff=rollback_diff,
        impact_projection=project_impact(rollback_diff),
        proposal=first_record.proposal,
        validation=first_record.validation,
        authority_decision=rollback_decision,
        resulting_snapshot=first,
        lifecycle_transition=rollback_transition,
        affected_execution_policy=execution_policy(
            rollback_decision,
            first,
            status=MeasurementStatus.NOT_APPLICABLE,
        ),
        reproduction=ReproductionRecord.non_runnable(
            first.snapshot_id, unavailable=IdentityAvailability.NOT_MEASURED
        ),
    )
    rollback_entry = ledger.append(rollback_record)

    revoke_decision = authority_decision(
        plane,
        first,
        AuthorityDecisionAction.REVOKE,
        4,
        disposition=ExecutionDisposition.QUARANTINE,
    )
    revoke_transition = plane.revoke_snapshot(first.snapshot_id, revoke_decision)
    classifications = plane.classify_pinned_executions(first.snapshot_id)
    revoke_record = GovernedEvolutionRecord(
        action=AuthorityDecisionAction.REVOKE,
        change_reason_evidence_identity=revoke_decision.evidence_identity,
        source_observations=(),
        source_verifications=(),
        prior_snapshot=first,
        semantic_diff=None,
        impact_projection=None,
        proposal=first_record.proposal,
        validation=first_record.validation,
        authority_decision=revoke_decision,
        resulting_snapshot=first,
        lifecycle_transition=revoke_transition,
        affected_execution_policy=execution_policy(
            revoke_decision,
            first,
            classifications=classifications,
        ),
        reproduction=ReproductionRecord.non_runnable(
            first.snapshot_id, unavailable=IdentityAvailability.UNKNOWN
        ),
    )
    revoke_entry = ledger.append(revoke_record)

    assert ledger.entries[: len(history_before)] == history_before
    assert rollback_entry.previous_entry_id == history_before[-1].entry_id
    assert revoke_entry.previous_entry_id == rollback_entry.entry_id
    assert [entry.record.action for entry in ledger.entries[-2:]] == [
        AuthorityDecisionAction.ROLLBACK,
        AuthorityDecisionAction.REVOKE,
    ]
    assert revoke_record.affected_execution_policy.classifications
    assert all(
        item.authority_decision_id == revoke_decision.decision_id
        for item in revoke_record.affected_execution_policy.classifications
    )
    assert ledger.verify_integrity()


def test_replay_and_explanation_reproduce_exact_identity_without_prose() -> None:
    ledger, _plane, _first, second, _first_record, _second_record = (
        two_promotion_scenario()
    )
    replayed = EvolutionLedger.replay(ledger.entries)
    entry = ledger.entries[-1]
    explanation = ledger.explain(entry.entry_id)
    replayed_explanation = replayed.explain(entry.entry_id)

    assert replayed.to_json() == ledger.to_json()
    assert replayed.ledger_id == ledger.ledger_id
    assert explanation.to_json() == replayed_explanation.to_json()
    assert explanation.resulting_snapshot_id == second.snapshot_id
    assert entry.record.semantic_diff is not None
    assert explanation.semantic_diff_id == entry.record.semantic_diff.diff_id
    assert explanation.reproduction.is_runnable
    assert explanation.reproduction.identity_for(
        ReproductionComponent.FACTORY_SOURCE
    ) == "git:factory-commit-abc"
    assert explanation.reproduction.identity_for(
        ReproductionComponent.REQUIREMENT
    ) == "requirement:REQ-M2.5F"
    assert explanation.reproduction.identity_for(
        ReproductionComponent.GOVERNANCE_SNAPSHOT
    ) == second.snapshot_id
    assert explanation.reproduction.replay_identity == (
        entry.record.reproduction.reproduction_id
    )


def test_unknown_not_measured_and_unknown_impact_remain_explicit() -> None:
    ledger, _plane, first, second, _first_record, second_record = (
        two_promotion_scenario()
    )
    assert second_record.impact_projection is not None
    assert second_record.impact_projection.has_unknown_impact
    assert second_record.impact_projection.unknown_impact_ids == ("FACT-limit",)

    partial = ReproductionRecord.non_runnable(
        first.snapshot_id,
        unavailable=IdentityAvailability.NOT_MEASURED,
        available_identities={
            ReproductionComponent.REQUIREMENT: "requirement:REQ-M2.5F"
        },
    )
    assert not partial.is_runnable
    assert partial.fact(ReproductionComponent.FACTORY_SOURCE).availability is (
        IdentityAvailability.NOT_MEASURED
    )
    assert partial.fact(ReproductionComponent.FACTORY_SOURCE).identity is None
    assert partial.fact(ReproductionComponent.REQUIREMENT).availability is (
        IdentityAvailability.EXACT
    )

    not_measured = AffectedExecutionPolicy(
        target_snapshot_id=second.snapshot_id,
        authority_decision_id=second_record.authority_decision.decision_id,
        measurement_status=MeasurementStatus.NOT_MEASURED,
    )
    assert not_measured.to_dict()["measurement_status"] == "NOT_MEASURED"
    assert not_measured.classifications == ()
    assert ledger.to_dict()["entries"][1]["record"]["impact_projection"][
        "has_unknown_impact"
    ] is True


def test_reproduction_and_cross_object_identity_mismatches_fail_closed() -> None:
    ledger, _plane, first, second, _first_record, second_record = (
        two_promotion_scenario()
    )
    fingerprint = second_record.reproduction.execution_fingerprint
    assert fingerprint is not None
    wrong = tuple(
        ReproductionIdentity.exact(
            item.component,
            "GOVERNANCE-SNAPSHOT-wrong"
            if item.component is ReproductionComponent.GOVERNANCE_SNAPSHOT
            else item.identity or "unreachable",
        )
        for item in second_record.reproduction.identities
    )
    with pytest.raises(EvolutionLedgerError, match="does not match"):
        ReproductionRecord(wrong, fingerprint)

    with pytest.raises(EvolutionLedgerError, match="different semantic diff"):
        GovernedEvolutionRecord(
            action=second_record.action,
            change_reason_evidence_identity=second_record.change_reason_evidence_identity,
            source_observations=second_record.source_observations,
            source_verifications=second_record.source_verifications,
            prior_snapshot=first,
            semantic_diff=second_record.semantic_diff,
            impact_projection=project_impact(diff_governance_snapshots(second, first)),
            proposal=second_record.proposal,
            validation=second_record.validation,
            authority_decision=second_record.authority_decision,
            resulting_snapshot=second,
            lifecycle_transition=second_record.lifecycle_transition,
            affected_execution_policy=second_record.affected_execution_policy,
            reproduction=second_record.reproduction,
        )
    assert ledger.verify_integrity()
