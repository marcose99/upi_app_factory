from __future__ import annotations

import datetime as dt
import decimal
from typing import Any, overload, cast

import pytest

from factory.application_engineering.failed_debit_capability import (
    AcceptResolutionCommand,
    CaseVersion,
    CloseDisputeCommand,
    CreateDisputeCommand,
    DisputeCase,
    DisputeApplicationService,
    DisputeDomainError,
    DisputeId,
    DisputeReason,
    DisputeState,
    DuplicateDisputeError,
    EvidenceItem,
    GetDisputeQuery,
    InMemoryDisputeCaseRepository,
    InMemoryIdempotencyPort,
    InvalidTransitionError,
    Money,
    ProposeResolutionCommand,
    RejectResolutionCommand,
    ResolutionDecision,
    ResolutionKind,
    SearchDisputesQuery,
    StartInvestigationCommand,
    SubmitEvidenceCommand,
    TerminalStateError,
    TransactionReference,
    ValidateDisputeCommand,
)
from factory.application_engineering.local_platform_kernel import (
    AuthorizationDenied,
    FictionalLocalAuthorizer,
    OptimisticConcurrencyError,
    Principal,
)


NOW = dt.datetime(2026, 7, 17, 4, 30, tzinfo=dt.timezone.utc)


def principal(*roles: str) -> Principal:
    return Principal("fictional-operator", frozenset(roles))


def service() -> DisputeApplicationService:
    grants = {
        "case_worker": {
            "dispute.create",
            "dispute.read",
            "dispute.search",
            "dispute.timeline",
            "dispute.audit",
            "dispute.evidence.submit",
            "dispute.validate",
            "dispute.investigate",
            "dispute.resolve",
            "dispute.close",
        }
    }
    return DisputeApplicationService(
        InMemoryDisputeCaseRepository(),
        FictionalLocalAuthorizer(grants),
        InMemoryIdempotencyPort(),
        lambda: NOW,
    )


def create_command(idempotency_key: str = "idem-create") -> CreateDisputeCommand:
    return CreateDisputeCommand(
        principal=principal("case_worker"),
        idempotency_key=idempotency_key,
        correlation_id="corr-55",
        expected_version=None,
        dispute_id=DisputeId("DISP-ABCDEF123456"),
        transaction_reference=TransactionReference("TXN-FAILED0000001"),
        amount=Money.of("125.50"),
        reason=DisputeReason.NO_CREDIT_AFTER_DEBIT,
    )


def evidence(evidence_id: str, evidence_type: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source=f"fictional_{evidence_type}",
        summary=f"Fictional {evidence_type} observation",
        observed_at=NOW,
    )


@overload
def command(command_type: type[ValidateDisputeCommand], dispute_id: DisputeId, expected: int, idem: str) -> ValidateDisputeCommand: ...


@overload
def command(
    command_type: type[StartInvestigationCommand], dispute_id: DisputeId, expected: int, idem: str
) -> StartInvestigationCommand: ...


@overload
def command(command_type: type[AcceptResolutionCommand], dispute_id: DisputeId, expected: int, idem: str) -> AcceptResolutionCommand: ...


@overload
def command(command_type: type[CloseDisputeCommand], dispute_id: DisputeId, expected: int, idem: str) -> CloseDisputeCommand: ...


@overload
def command(
    command_type: type[SubmitEvidenceCommand],
    dispute_id: DisputeId,
    expected: int,
    idem: str,
    *,
    evidence: EvidenceItem,
) -> SubmitEvidenceCommand: ...


@overload
def command(
    command_type: type[ProposeResolutionCommand],
    dispute_id: DisputeId,
    expected: int,
    idem: str,
    *,
    decision: ResolutionDecision,
) -> ProposeResolutionCommand: ...


@overload
def command(
    command_type: type[RejectResolutionCommand],
    dispute_id: DisputeId,
    expected: int,
    idem: str,
    *,
    rationale: str,
) -> RejectResolutionCommand: ...


def command(
    command_type: type[
        ValidateDisputeCommand
        | StartInvestigationCommand
        | AcceptResolutionCommand
        | CloseDisputeCommand
        | SubmitEvidenceCommand
        | ProposeResolutionCommand
        | RejectResolutionCommand
    ],
    dispute_id: DisputeId,
    expected: int,
    idem: str,
    **kwargs: object,
) -> (
    ValidateDisputeCommand
    | StartInvestigationCommand
    | AcceptResolutionCommand
    | CloseDisputeCommand
    | SubmitEvidenceCommand
    | ProposeResolutionCommand
    | RejectResolutionCommand
):
    actor = principal("case_worker")
    version = CaseVersion(expected)
    if command_type is SubmitEvidenceCommand:
        evidence_value = kwargs.get("evidence")
        if not isinstance(evidence_value, EvidenceItem):
            raise TypeError("SubmitEvidenceCommand requires EvidenceItem evidence")
        return SubmitEvidenceCommand(actor, idem, "corr-55", version, dispute_id, evidence_value)
    if command_type is ProposeResolutionCommand:
        decision = kwargs.get("decision")
        if not isinstance(decision, ResolutionDecision):
            raise TypeError("ProposeResolutionCommand requires ResolutionDecision decision")
        return ProposeResolutionCommand(actor, idem, "corr-55", version, dispute_id, decision)
    if command_type is RejectResolutionCommand:
        rationale = kwargs.get("rationale")
        if not isinstance(rationale, str):
            raise TypeError("RejectResolutionCommand requires string rationale")
        return RejectResolutionCommand(actor, idem, "corr-55", version, dispute_id, rationale)
    if command_type is ValidateDisputeCommand:
        return ValidateDisputeCommand(actor, idem, "corr-55", version, dispute_id)
    if command_type is StartInvestigationCommand:
        return StartInvestigationCommand(actor, idem, "corr-55", version, dispute_id)
    if command_type is AcceptResolutionCommand:
        return AcceptResolutionCommand(actor, idem, "corr-55", version, dispute_id)
    return CloseDisputeCommand(actor, idem, "corr-55", version, dispute_id)


def create_validated_case(app: DisputeApplicationService) -> DisputeCase:
    case, _ = app.create(create_command())
    case, _ = app.validate(command(ValidateDisputeCommand, case.dispute_id, case.version.value, "idem-validate"))
    return case


def submit_complete_evidence(app: DisputeApplicationService, case: DisputeCase) -> DisputeCase:
    for index, evidence_type in enumerate(["switch_failure", "core_ledger", "customer_statement"], start=1):
        case, _ = app.submit_evidence(
            command(
                SubmitEvidenceCommand,
                case.dispute_id,
                case.version.value,
                f"idem-evidence-{index}",
                evidence=evidence(f"EVD-VALID000{index}", evidence_type),
            )
        )
    return case


def proposed_case(app: DisputeApplicationService) -> DisputeCase:
    case = submit_complete_evidence(app, create_validated_case(app))
    decision = ResolutionDecision(
        decision_id="RSL-VALID0001",
        kind=ResolutionKind.CUSTOMER_CREDIT,
        amount=Money.of("125.50"),
        rationale="Fictional ledger and switch traces agree no credit occurred.",
        decided_by="fictional-operator",
    )
    case, _ = app.propose_resolution(
        command(ProposeResolutionCommand, case.dispute_id, case.version.value, "idem-resolution", decision=decision)
    )
    return case


def test_full_valid_lifecycle_emits_event_for_every_accepted_change() -> None:
    app = service()
    case = proposed_case(app)
    case, _ = app.accept_resolution(
        command(AcceptResolutionCommand, case.dispute_id, case.version.value, "idem-accept")
    )
    case, _ = app.close(command(CloseDisputeCommand, case.dispute_id, case.version.value, "idem-close"))

    assert case.state is DisputeState.CLOSED
    assert case.version.value == 8
    assert [event.event_type for event in case.timeline] == [
        "case_received",
        "case_validated",
        "evidence_submitted",
        "evidence_submitted",
        "evidence_submitted",
        "resolution_proposed",
        "case_resolved",
        "case_closed",
    ]


@pytest.mark.parametrize(
    ("amount", "currency"),
    [("0.00", "INR"), ("-1.00", "INR"), ("10.00", "USD")],
)
def test_money_requires_positive_inr(amount: str, currency: str) -> None:
    with pytest.raises(ValueError):
        Money.of(amount, currency)


def test_duplicate_transaction_reference_is_rejected() -> None:
    app = service()
    app.create(create_command("idem-create-1"))
    duplicate = CreateDisputeCommand(
        principal=principal("case_worker"),
        idempotency_key="idem-create-2",
        correlation_id="corr-55",
        expected_version=None,
        dispute_id=DisputeId("DISP-ZYXWVU654321"),
        transaction_reference=TransactionReference("TXN-FAILED0000001"),
        amount=Money.of("125.50"),
        reason=DisputeReason.NO_CREDIT_AFTER_DEBIT,
    )

    with pytest.raises(DuplicateDisputeError):
        app.create(duplicate)


def test_immutable_transaction_reference_and_case_type_are_frozen() -> None:
    app = service()
    case, _ = app.create(create_command())

    with pytest.raises(Exception):
        cast(Any, case).transaction_reference = TransactionReference("TXN-CHANGED000001")
    with pytest.raises(Exception):
        cast(Any, case).case_type = "other"


def test_invalid_transitions_are_rejected() -> None:
    app = service()
    case, _ = app.create(create_command())

    with pytest.raises(InvalidTransitionError):
        app.start_investigation(
            command(StartInvestigationCommand, case.dispute_id, case.version.value, "idem-investigate")
        )


def test_evidence_incomplete_blocks_investigation() -> None:
    app = service()
    case = create_validated_case(app)
    case, _ = app.submit_evidence(
        command(
            SubmitEvidenceCommand,
            case.dispute_id,
            case.version.value,
            "idem-evidence-one",
            evidence=evidence("EVD-PARTIAL01", "switch_failure"),
        )
    )

    assert case.state is DisputeState.EVIDENCE_PENDING
    with pytest.raises(DisputeDomainError):
        app.start_investigation(
            command(StartInvestigationCommand, case.dispute_id, case.version.value, "idem-investigate")
        )


def test_complete_evidence_auto_starts_investigation() -> None:
    app = service()
    case = submit_complete_evidence(app, create_validated_case(app))

    assert case.state is DisputeState.INVESTIGATION


def test_resolution_policy_rejects_excess_amount() -> None:
    app = service()
    case = submit_complete_evidence(app, create_validated_case(app))
    decision = ResolutionDecision(
        decision_id="RSL-TOOHIGH01",
        kind=ResolutionKind.CUSTOMER_CREDIT,
        amount=Money.of("126.00"),
        rationale="Too high.",
        decided_by="fictional-operator",
    )

    with pytest.raises(DisputeDomainError):
        app.propose_resolution(
            command(ProposeResolutionCommand, case.dispute_id, case.version.value, "idem-too-high", decision=decision)
        )


def test_terminal_closed_case_is_protected() -> None:
    app = service()
    case = proposed_case(app)
    case, _ = app.accept_resolution(
        command(AcceptResolutionCommand, case.dispute_id, case.version.value, "idem-accept")
    )
    case, _ = app.close(command(CloseDisputeCommand, case.dispute_id, case.version.value, "idem-close"))

    with pytest.raises(TerminalStateError):
        app.close(command(CloseDisputeCommand, case.dispute_id, case.version.value, "idem-close-again"))


def test_idempotency_replays_without_second_mutation() -> None:
    app = service()
    first, replayed_first = app.create(create_command("idem-replay"))
    second, replayed_second = app.create(create_command("idem-replay"))

    assert first == second
    assert replayed_first is False
    assert replayed_second is True
    assert len(second.timeline) == 1


def test_idempotency_rejects_key_reuse_with_changed_payload() -> None:
    app = service()
    app.create(create_command("idem-reuse"))
    changed = dataclasses_replace_create(create_command("idem-reuse"), amount=Money.of("126.00"))

    with pytest.raises(DisputeDomainError):
        app.create(changed)


def dataclasses_replace_create(command_obj: CreateDisputeCommand, *, amount: Money | None = None) -> CreateDisputeCommand:
    return CreateDisputeCommand(
        principal=command_obj.principal,
        idempotency_key=command_obj.idempotency_key,
        correlation_id=command_obj.correlation_id,
        expected_version=command_obj.expected_version,
        dispute_id=command_obj.dispute_id,
        transaction_reference=command_obj.transaction_reference,
        amount=command_obj.amount if amount is None else amount,
        reason=command_obj.reason,
    )


def test_optimistic_concurrency_conflict_is_reported() -> None:
    app = service()
    case, _ = app.create(create_command())

    with pytest.raises(OptimisticConcurrencyError):
        app.validate(command(ValidateDisputeCommand, case.dispute_id, 99, "idem-conflict"))


def test_queries_search_timeline_and_audit_are_authorized() -> None:
    app = service()
    case = proposed_case(app)
    query = GetDisputeQuery(principal=principal("case_worker"), correlation_id="corr-55", dispute_id=case.dispute_id)

    assert app.get(query).dispute_id == case.dispute_id
    assert app.search(SearchDisputesQuery(principal=principal("case_worker"), correlation_id="corr-55", state=case.state))
    assert len(app.timeline(query)) == case.version.value
    assert app.audit(query)["event_count"] == case.version.value


def test_authorization_is_enforced_per_operation() -> None:
    app = service()
    unauthorized = CreateDisputeCommand(
        principal=principal("viewer"),
        idempotency_key="idem-denied",
        correlation_id="corr-55",
        expected_version=None,
        dispute_id=DisputeId("DISP-DENIED123456"),
        transaction_reference=TransactionReference("TXN-DENIED0000001"),
        amount=Money.of("1.00"),
        reason=DisputeReason.NO_CREDIT_AFTER_DEBIT,
    )

    with pytest.raises(AuthorizationDenied):
        app.create(unauthorized)


def test_replay_restores_state_version_and_timeline() -> None:
    app = service()
    case = proposed_case(app)

    replayed = case.replay()

    assert replayed.state == case.state
    assert replayed.version == case.version
    assert replayed.timeline == case.timeline


def test_all_transition_table_paths_are_covered() -> None:
    app = service()
    accepted = proposed_case(app)
    accepted, _ = app.accept_resolution(
        command(AcceptResolutionCommand, accepted.dispute_id, accepted.version.value, "idem-accept")
    )
    accepted, _ = app.close(
        command(CloseDisputeCommand, accepted.dispute_id, accepted.version.value, "idem-close-resolved")
    )
    rejected_app = service()
    rejected = proposed_case(rejected_app)
    rejected, _ = rejected_app.reject_resolution(
        command(
            RejectResolutionCommand,
            rejected.dispute_id,
            rejected.version.value,
            "idem-reject",
            rationale="Fictional evidence review rejected the proposed credit.",
        )
    )

    assert accepted.state is DisputeState.CLOSED
    assert rejected.state is DisputeState.REJECTED


def test_deterministic_fuzz_invariant_loop() -> None:
    for index in range(25):
        app = service()
        amount = decimal.Decimal(index + 1) / decimal.Decimal("2")
        create = CreateDisputeCommand(
            principal=principal("case_worker"),
            idempotency_key=f"idem-create-{index}",
            correlation_id=f"corr-{index}",
            expected_version=None,
            dispute_id=DisputeId(f"DISP-FUZZ{index:08d}"),
            transaction_reference=TransactionReference(f"TXN-FUZZ{index:010d}"),
            amount=Money.of(amount),
            reason=DisputeReason.NO_CREDIT_AFTER_DEBIT,
        )
        case, _ = app.create(create)
        case, _ = app.validate(command(ValidateDisputeCommand, case.dispute_id, case.version.value, f"idem-val-{index}"))

        assert case.amount.amount > decimal.Decimal("0.00")
        assert case.amount.currency == "INR"
        assert case.transaction_reference.value == f"TXN-FUZZ{index:010d}"
        assert len({event.event_id for event in case.timeline}) == len(case.timeline)
        assert [event.case_version for event in case.timeline] == list(range(1, case.version.value + 1))
