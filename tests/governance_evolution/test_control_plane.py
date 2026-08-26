from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from factory.documentation import canonical_json
from factory.governance_evolution import (
    AuthorityDecision,
    AuthorityDecisionAction,
    AuthorityRegistry,
    ControlPlaneError,
    ExecutionDisposition,
    ExecutionFingerprint,
    ExecutionPin,
    ExecutionPinError,
    GovernanceControlPlane,
    GovernanceLifecycleState,
    GovernanceProposal,
    GovernanceSnapshot,
    GovernanceValidation,
    InvalidLifecycleTransition,
    LifecycleEvent,
    NO_ACTIVE_SNAPSHOT_ID,
    ProposalOrigin,
    SourceAuthorityContract,
    SourceMetadata,
    SourceObservation,
    SourceVerification,
    UnauthorizedGovernanceDecision,
    sha256_bytes,
)


POLICY_BYTES = b'{"authority":"governed-policy-owner","revision":1}'
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


def verification(
    authority_registry: AuthorityRegistry, content: bytes = POLICY_BYTES
) -> SourceVerification:
    metadata = SourceMetadata(
        authority_id="AUTHORITY-policy-owner",
        source_id="SOURCE-policy",
        revision="revision:1",
        content_sha256=sha256_bytes(content),
        source_type="SIGNED_POLICY_BUNDLE",
    )
    return authority_registry.verify(SourceObservation(content, metadata))


def snapshot(
    authority_registry: AuthorityRegistry,
    version: int,
    *,
    predecessor: GovernanceSnapshot | None = None,
) -> GovernanceSnapshot:
    binding = authority_registry.contract_for("SOURCE-policy").to_source_binding()
    predecessor_id = predecessor.snapshot_id if predecessor is not None else None
    return GovernanceSnapshot(
        version_id=f"policy:{version}",
        payload={
            "facts": {"FACT-limit": {"value": version * 10}},
            "rules": {"RULE-limit": {"effect": "DENY_ABOVE_LIMIT"}},
        },
        source_bindings=(binding,),
        previous_snapshot_id=predecessor_id,
        supersedes_snapshot_id=predecessor_id,
    )


def proposal(governed: GovernanceSnapshot, version: int) -> GovernanceProposal:
    return GovernanceProposal(
        proposal_id=f"PROPOSAL-{version}",
        target_snapshot_id=governed.snapshot_id,
        evidence_identity=f"PROPOSAL-EVIDENCE-{version}",
        proposer_identity="MODEL-non-authoritative" if version == 1 else "TOOL-diff",
        origin=(
            ProposalOrigin.AI if version == 1 else ProposalOrigin.DETERMINISTIC_TOOL
        ),
    )


def validation(
    governed: GovernanceSnapshot,
    proposed: GovernanceProposal,
    version: int,
    *,
    passed: bool = True,
) -> GovernanceValidation:
    return GovernanceValidation(
        validation_id=f"VALIDATION-{version}",
        target_snapshot_id=governed.snapshot_id,
        proposal_id=proposed.proposal_id,
        evidence_identity=f"VALIDATION-EVIDENCE-{version}",
        validator_identity="TOOL-deterministic-qualification-v1",
        passed=passed,
    )


def decision(
    plane: GovernanceControlPlane,
    governed: GovernanceSnapshot,
    action: AuthorityDecisionAction,
    sequence: int,
    *,
    proposed: GovernanceProposal | None = None,
    qualified: GovernanceValidation | None = None,
    disposition: ExecutionDisposition | None = None,
    authority_id: str = DECISION_AUTHORITY,
    expected_active_snapshot_id: str | None = None,
) -> AuthorityDecision:
    return AuthorityDecision(
        decision_id=f"AUTHORITY-DECISION-{sequence}",
        authority_id=authority_id,
        action=action,
        target_snapshot_id=governed.snapshot_id,
        evidence_identity=f"AUTHORITY-DECISION-EVIDENCE-{sequence}",
        expected_active_snapshot_id=(
            plane.expected_active_snapshot_id
            if expected_active_snapshot_id is None
            else expected_active_snapshot_id
        ),
        proposal_id=proposed.proposal_id if proposed is not None else None,
        validation_id=qualified.validation_id if qualified is not None else None,
        execution_disposition=disposition,
    )


def qualify(
    plane: GovernanceControlPlane,
    authority_registry: AuthorityRegistry,
    governed: GovernanceSnapshot,
    version: int,
) -> tuple[GovernanceProposal, GovernanceValidation]:
    plane.observe_snapshot(governed)
    plane.verify_snapshot(governed.snapshot_id, verification(authority_registry))
    proposed = proposal(governed, version)
    plane.propose_snapshot(governed.snapshot_id, proposed)
    qualified = validation(governed, proposed, version)
    plane.validate_snapshot(governed.snapshot_id, qualified)
    return proposed, qualified


def promote(
    plane: GovernanceControlPlane,
    governed: GovernanceSnapshot,
    proposed: GovernanceProposal,
    qualified: GovernanceValidation,
    sequence: int,
) -> None:
    plane.promote_snapshot(
        governed.snapshot_id,
        decision(
            plane,
            governed,
            AuthorityDecisionAction.PROMOTE,
            sequence,
            proposed=proposed,
            qualified=qualified,
        ),
    )


def running_plane() -> tuple[
    GovernanceControlPlane,
    AuthorityRegistry,
    GovernanceSnapshot,
]:
    authority_registry = registry()
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    governed = snapshot(authority_registry, 1)
    proposed, qualified = qualify(plane, authority_registry, governed, 1)
    promote(plane, governed, proposed, qualified, 1)
    return plane, authority_registry, governed


def start(plane: GovernanceControlPlane, execution_id: str) -> ExecutionPin:
    return plane.start_execution(
        execution_id,
        factory_source_identity="git:factory-commit-abc",
        requirement_identity="requirements:sha256-abc",
        evidence_snapshot_identity="evidence:sha256-def",
        tool_config_identity="tool-config:sha256-ghi",
    )


def test_explicit_lifecycle_is_audited_hash_chained_and_canonical() -> None:
    authority_registry = registry()
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    governed = snapshot(authority_registry, 1)

    observed = plane.observe_snapshot(governed)
    assert observed.to_state is GovernanceLifecycleState.OBSERVED_UNVERIFIED
    verified = plane.verify_snapshot(governed.snapshot_id, verification(authority_registry))
    assert verified.to_state is GovernanceLifecycleState.AUTHORITY_VERIFIED
    proposed = proposal(governed, 1)
    assert plane.propose_snapshot(governed.snapshot_id, proposed).state is (
        GovernanceLifecycleState.PROPOSED
    )
    qualified = validation(governed, proposed, 1)
    assert plane.validate_snapshot(governed.snapshot_id, qualified).state is (
        GovernanceLifecycleState.VALIDATED
    )
    promote(plane, governed, proposed, qualified, 1)

    assert plane.snapshot_state(governed.snapshot_id) is GovernanceLifecycleState.ACTIVE
    assert [item.to_state for item in plane.transition_history] == [
        GovernanceLifecycleState.OBSERVED_UNVERIFIED,
        GovernanceLifecycleState.AUTHORITY_VERIFIED,
        GovernanceLifecycleState.PROPOSED,
        GovernanceLifecycleState.VALIDATED,
        GovernanceLifecycleState.ACTIVE,
    ]
    assert all(
        current.previous_transition_id == previous.transition_id
        for previous, current in zip(
            plane.transition_history, plane.transition_history[1:]
        )
    )
    assert plane.transition_history[-1].event is LifecycleEvent.PROMOTE
    assert plane.to_json() == canonical_json(plane.to_dict())
    projection = plane.to_dict()
    assert projection["authority_decisions"][0]["evidence_identity"] == (
        "AUTHORITY-DECISION-EVIDENCE-1"
    )
    assert projection["proposals"][0]["origin"] == "AI_NON_AUTHORITATIVE"
    assert projection["validations"][0]["passed"] is True
    assert projection["snapshots"][0]["snapshot_id"] == governed.snapshot_id


def test_ai_proposal_is_non_authoritative_and_cannot_self_promote() -> None:
    authority_registry = registry()
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    governed = snapshot(authority_registry, 1)
    proposed, qualified = qualify(plane, authority_registry, governed, 1)

    assert proposed.origin is ProposalOrigin.AI
    with pytest.raises(UnauthorizedGovernanceDecision, match="explicit governed"):
        plane.promote_snapshot(governed.snapshot_id, proposed)  # type: ignore[arg-type]
    with pytest.raises(UnauthorizedGovernanceDecision, match="configured authority"):
        plane.promote_snapshot(
            governed.snapshot_id,
            decision(
                plane,
                governed,
                AuthorityDecisionAction.PROMOTE,
                1,
                proposed=proposed,
                qualified=qualified,
                authority_id="MODEL-non-authoritative",
            ),
        )
    assert plane.snapshot_state(governed.snapshot_id) is GovernanceLifecycleState.VALIDATED


def test_new_activation_changes_new_executions_only_and_blocks_pin_mutation() -> None:
    plane, authority_registry, first = running_plane()
    old_pin = start(plane, "EXECUTION-old")
    old_pin_projection = old_pin.to_dict()
    second = snapshot(authority_registry, 2, predecessor=first)
    proposed, qualified = qualify(plane, authority_registry, second, 2)
    promote(plane, second, proposed, qualified, 2)
    new_pin = start(plane, "EXECUTION-new")

    assert old_pin.governance_snapshot_id == first.snapshot_id
    assert old_pin.to_dict() == old_pin_projection
    assert new_pin.governance_snapshot_id == second.snapshot_id
    assert plane.snapshot_state(first.snapshot_id) is GovernanceLifecycleState.SUPERSEDED
    assert plane.snapshot_state(second.snapshot_id) is GovernanceLifecycleState.ACTIVE
    assert plane.assert_execution_snapshot("EXECUTION-old", first.snapshot_id) is old_pin
    with pytest.raises(ExecutionPinError, match="cross-snapshot"):
        plane.assert_execution_snapshot("EXECUTION-old", second.snapshot_id)
    with pytest.raises(ExecutionPinError, match="already has"):
        plane.pin_execution("EXECUTION-old", new_pin.execution_fingerprint)
    with pytest.raises(FrozenInstanceError):
        old_pin.governance_snapshot_id = second.snapshot_id  # type: ignore[misc]


def test_cross_snapshot_fingerprint_and_unpinned_normative_execution_fail_closed() -> None:
    plane, authority_registry, first = running_plane()
    second = snapshot(authority_registry, 2, predecessor=first)
    wrong_fingerprint = ExecutionFingerprint.for_snapshot(
        factory_source_identity="git:factory-commit-abc",
        requirement_identity="requirements:sha256-abc",
        governance_snapshot=second,
        evidence_snapshot_identity="evidence:sha256-def",
        tool_config_identity="tool-config:sha256-ghi",
    )

    with pytest.raises(ExecutionPinError, match="cross-snapshot"):
        plane.pin_execution("EXECUTION-cross", wrong_fingerprint)
    with pytest.raises(ExecutionPinError, match="before governance pinning"):
        plane.require_execution_pin("EXECUTION-unpinned")


@pytest.mark.parametrize(
    "disposition",
    (
        ExecutionDisposition.CONTINUE,
        ExecutionDisposition.QUARANTINE,
        ExecutionDisposition.RESTART_REQUIRED,
    ),
)
def test_material_revocation_classifies_runs_without_rewriting_pin(
    disposition: ExecutionDisposition,
) -> None:
    plane, _authority_registry, governed = running_plane()
    pin = start(plane, "EXECUTION-pinned")
    pin_before = pin.to_dict()
    revoke = decision(
        plane,
        governed,
        AuthorityDecisionAction.REVOKE,
        10,
        disposition=disposition,
    )

    plane.revoke_snapshot(governed.snapshot_id, revoke)
    classification = plane.classify_execution("EXECUTION-pinned")

    assert plane.snapshot_state(governed.snapshot_id) is GovernanceLifecycleState.REVOKED
    assert plane.active_snapshot_id is None
    assert classification.disposition is disposition
    assert classification.authority_decision_id == revoke.decision_id
    assert plane.require_execution_pin("EXECUTION-pinned").to_dict() == pin_before
    with pytest.raises(InvalidLifecycleTransition):
        plane.revoke_snapshot(
            governed.snapshot_id,
            decision(
                plane,
                governed,
                AuthorityDecisionAction.REVOKE,
                11,
                disposition=disposition,
            ),
        )


def test_rollback_reactivates_prior_object_and_preserves_all_history_and_pins() -> None:
    plane, authority_registry, first = running_plane()
    first_pin = start(plane, "EXECUTION-first")
    second = snapshot(authority_registry, 2, predecessor=first)
    proposed, qualified = qualify(plane, authority_registry, second, 2)
    promote(plane, second, proposed, qualified, 2)
    second_pin = start(plane, "EXECUTION-second")
    history_before = plane.transition_history

    rollback = decision(
        plane,
        first,
        AuthorityDecisionAction.ROLLBACK,
        3,
    )
    transition = plane.rollback_to_snapshot(first.snapshot_id, rollback)
    post_rollback_pin = start(plane, "EXECUTION-after-rollback")

    assert transition.event is LifecycleEvent.ROLLBACK
    assert plane.active_snapshot is first
    assert plane.snapshot_state(first.snapshot_id) is GovernanceLifecycleState.ACTIVE
    assert plane.snapshot_state(second.snapshot_id) is GovernanceLifecycleState.SUPERSEDED
    assert plane.transition_history[: len(history_before)] == history_before
    assert plane.require_execution_pin("EXECUTION-first") is first_pin
    assert plane.require_execution_pin("EXECUTION-second") is second_pin
    assert second_pin.governance_snapshot_id == second.snapshot_id
    assert post_rollback_pin.governance_snapshot_id == first.snapshot_id
    assert [item.event for item in plane.snapshot_history(first.snapshot_id)].count(
        LifecycleEvent.ROLLBACK
    ) == 1


def test_stale_unverified_ambiguous_and_invalid_transitions_fail_closed() -> None:
    authority_registry = registry()
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    governed = snapshot(authority_registry, 1)
    plane.observe_snapshot(governed)
    history_before = plane.transition_history
    stale = verification(authority_registry, b"changed source bytes")

    with pytest.raises(ControlPlaneError, match="stale or unverified"):
        plane.verify_snapshot(governed.snapshot_id, stale)
    assert plane.transition_history == history_before
    with pytest.raises(InvalidLifecycleTransition, match="AUTHORITY_VERIFIED"):
        plane.propose_snapshot(governed.snapshot_id, proposal(governed, 1))
    with pytest.raises(ControlPlaneError, match="version_id"):
        plane.observe_snapshot(
            GovernanceSnapshot(
                version_id=governed.version_id,
                payload={"facts": {"FACT-other": True}},
                source_bindings=governed.source_bindings,
            )
        )


def test_stale_authority_decision_and_cross_snapshot_qualification_are_rejected() -> None:
    plane, authority_registry, first = running_plane()
    second = snapshot(authority_registry, 2, predecessor=first)
    proposed, qualified = qualify(plane, authority_registry, second, 2)
    stale = decision(
        plane,
        second,
        AuthorityDecisionAction.PROMOTE,
        2,
        proposed=proposed,
        qualified=qualified,
        expected_active_snapshot_id=NO_ACTIVE_SNAPSHOT_ID,
    )
    history_before = plane.transition_history

    with pytest.raises(UnauthorizedGovernanceDecision, match="stale"):
        plane.promote_snapshot(second.snapshot_id, stale)
    assert plane.transition_history == history_before
    assert plane.snapshot_state(first.snapshot_id) is GovernanceLifecycleState.ACTIVE
    assert plane.snapshot_state(second.snapshot_id) is GovernanceLifecycleState.VALIDATED

    wrong_validation_decision = AuthorityDecision(
        decision_id="AUTHORITY-DECISION-wrong-validation",
        authority_id=DECISION_AUTHORITY,
        action=AuthorityDecisionAction.PROMOTE,
        target_snapshot_id=second.snapshot_id,
        evidence_identity="AUTHORITY-EVIDENCE-wrong-validation",
        expected_active_snapshot_id=first.snapshot_id,
        proposal_id=proposed.proposal_id,
        validation_id="VALIDATION-other-snapshot",
    )
    with pytest.raises(UnauthorizedGovernanceDecision, match="validation"):
        plane.promote_snapshot(second.snapshot_id, wrong_validation_decision)


def test_failed_qualification_and_explicit_quarantine_are_terminal() -> None:
    authority_registry = registry()
    plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
    governed = snapshot(authority_registry, 1)
    plane.observe_snapshot(governed)
    plane.verify_snapshot(governed.snapshot_id, verification(authority_registry))
    proposed = proposal(governed, 1)
    plane.propose_snapshot(governed.snapshot_id, proposed)
    failed = validation(governed, proposed, 1, passed=False)

    transition = plane.validate_snapshot(governed.snapshot_id, failed)

    assert transition.event is LifecycleEvent.QUALIFICATION_FAILED
    assert plane.snapshot_state(governed.snapshot_id) is (
        GovernanceLifecycleState.QUARANTINED
    )
    with pytest.raises(InvalidLifecycleTransition):
        plane.promote_snapshot(
            governed.snapshot_id,
            decision(
                plane,
                governed,
                AuthorityDecisionAction.PROMOTE,
                1,
                proposed=proposed,
                qualified=failed,
            ),
        )


def test_manual_quarantine_classifies_existing_run_and_preserves_pin() -> None:
    plane, _authority_registry, governed = running_plane()
    pin = start(plane, "EXECUTION-quarantined")
    quarantine = decision(
        plane,
        governed,
        AuthorityDecisionAction.QUARANTINE,
        20,
        disposition=ExecutionDisposition.QUARANTINE,
    )

    plane.quarantine_snapshot(governed.snapshot_id, quarantine)

    assert plane.classify_execution("EXECUTION-quarantined").disposition is (
        ExecutionDisposition.QUARANTINE
    )
    assert plane.require_execution_pin("EXECUTION-quarantined") is pin
    assert plane.snapshot_state(governed.snapshot_id) is (
        GovernanceLifecycleState.QUARANTINED
    )


def test_same_logical_operation_sequence_has_identical_serialization_and_digests() -> None:
    def build() -> GovernanceControlPlane:
        authority_registry = registry()
        plane = GovernanceControlPlane(authority_registry, (DECISION_AUTHORITY,))
        governed = snapshot(authority_registry, 1)
        proposed, qualified = qualify(plane, authority_registry, governed, 1)
        promote(plane, governed, proposed, qualified, 1)
        start(plane, "EXECUTION-1")
        return plane

    first = build()
    second = build()

    assert first.to_json() == second.to_json()
    assert first.control_plane_sha256 == second.control_plane_sha256
    assert [item.transition_id for item in first.transition_history] == [
        item.transition_id for item in second.transition_history
    ]
