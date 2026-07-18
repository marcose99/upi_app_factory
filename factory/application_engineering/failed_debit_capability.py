from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import decimal
import hashlib
import json
import re
from enum import Enum
from typing import Any, Callable, Protocol
from typing import cast

from factory.application_engineering.local_platform_kernel import (
    AuthorizationPort,
    OptimisticConcurrencyError,
    Principal,
)


class DisputeDomainError(ValueError):
    pass


class DuplicateDisputeError(DisputeDomainError):
    pass


class InvalidTransitionError(DisputeDomainError):
    pass


class TerminalStateError(DisputeDomainError):
    pass


class DisputeState(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    EVIDENCE_PENDING = "evidence_pending"
    INVESTIGATION = "investigation"
    RESOLUTION_PROPOSED = "resolution_proposed"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"


class DisputeReason(str, Enum):
    NO_CREDIT_AFTER_DEBIT = "no_credit_after_debit"
    DUPLICATE_DEBIT = "duplicate_debit"
    WRONG_BENEFICIARY = "wrong_beneficiary"
    REVERSAL_NOT_RECEIVED = "reversal_not_received"


class ResolutionKind(str, Enum):
    CUSTOMER_CREDIT = "customer_credit"
    REVERSAL_CONFIRMED = "reversal_confirmed"
    REJECT_CUSTOMER_CLAIM = "reject_customer_claim"


@dataclasses.dataclass(frozen=True)
class DisputeId:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"DISP-[A-Z0-9]{12}", self.value):
            raise ValueError("dispute id must match DISP-[A-Z0-9]{12}")


@dataclasses.dataclass(frozen=True)
class TransactionReference:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"TXN-[A-Z0-9]{10,24}", self.value):
            raise ValueError("transaction reference must be a fictional TXN-* reference")


@dataclasses.dataclass(frozen=True)
class Money:
    amount: decimal.Decimal
    currency: str = "INR"

    def __post_init__(self) -> None:
        if self.currency != "INR":
            raise ValueError("failed-debit disputes require INR")
        quantized = self.amount.quantize(decimal.Decimal("0.01"))
        if quantized <= decimal.Decimal("0.00"):
            raise ValueError("failed-debit dispute amount must be positive")
        object.__setattr__(self, "amount", quantized)

    @classmethod
    def of(cls, amount: str | int | decimal.Decimal, currency: str = "INR") -> Money:
        return cls(decimal.Decimal(str(amount)), currency)


@dataclasses.dataclass(frozen=True)
class CaseVersion:
    value: int = 0

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("case version cannot be negative")

    def next(self) -> CaseVersion:
        return CaseVersion(self.value + 1)


@dataclasses.dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    evidence_type: str
    source: str
    summary: str
    observed_at: dt.datetime

    def __post_init__(self) -> None:
        if not re.fullmatch(r"EVD-[A-Z0-9]{8,20}", self.evidence_id):
            raise ValueError("evidence id must be fictional and stable")
        if self.evidence_type not in EvidenceCompletenessPolicy.REQUIRED_TYPES:
            raise ValueError("unsupported evidence type")
        if not self.source or not self.summary:
            raise ValueError("evidence source and summary are required")
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence observed_at must be timezone-aware")


@dataclasses.dataclass(frozen=True)
class ResolutionDecision:
    decision_id: str
    kind: ResolutionKind
    amount: Money
    rationale: str
    decided_by: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"RSL-[A-Z0-9]{8,20}", self.decision_id):
            raise ValueError("resolution decision id must be fictional and stable")
        if not self.rationale or not self.decided_by:
            raise ValueError("resolution rationale and actor are required")


@dataclasses.dataclass(frozen=True)
class DomainEvent:
    event_id: str
    dispute_id: str
    event_type: str
    from_state: str
    to_state: str
    case_version: int
    occurred_at: str
    payload: dict[str, Any]


class EligibilityPolicy:
    ALLOWED_REASONS = frozenset(item.value for item in DisputeReason)

    def assert_eligible(self, reason: DisputeReason, amount: Money, case_type: str) -> None:
        if case_type != "failed_debit_no_credit":
            raise DisputeDomainError("only failed_debit_no_credit case type is supported")
        if reason.value not in self.ALLOWED_REASONS:
            raise DisputeDomainError("unsupported dispute reason")
        if amount.currency != "INR" or amount.amount <= decimal.Decimal("0.00"):
            raise DisputeDomainError("amount must be positive INR")


class DuplicateCasePolicy:
    def __init__(self, transaction_references: set[str] | None = None) -> None:
        self.transaction_references = set() if transaction_references is None else set(transaction_references)

    def assert_not_duplicate(self, reference: TransactionReference) -> None:
        if reference.value in self.transaction_references:
            raise DuplicateDisputeError("duplicate dispute for transaction reference")

    def remember(self, reference: TransactionReference) -> None:
        self.transaction_references.add(reference.value)


class EvidenceCompletenessPolicy:
    REQUIRED_TYPES = frozenset({"switch_failure", "core_ledger", "customer_statement"})

    def is_complete(self, evidence: tuple[EvidenceItem, ...]) -> bool:
        present = {item.evidence_type for item in evidence}
        return self.REQUIRED_TYPES.issubset(present)

    def missing_types(self, evidence: tuple[EvidenceItem, ...]) -> tuple[str, ...]:
        present = {item.evidence_type for item in evidence}
        return tuple(sorted(self.REQUIRED_TYPES - present))


class ResolutionPolicy:
    def assert_decision_allowed(self, case: DisputeCase, decision: ResolutionDecision) -> None:
        if case.state is not DisputeState.INVESTIGATION:
            raise DisputeDomainError("resolution can only be proposed during investigation")
        if decision.amount.amount > case.amount.amount:
            raise DisputeDomainError("resolution amount cannot exceed disputed amount")
        if decision.kind is ResolutionKind.REJECT_CUSTOMER_CLAIM and decision.amount.amount != case.amount.amount:
            raise DisputeDomainError("rejected claims keep the disputed amount for audit comparability")


TRANSITION_TABLE: dict[tuple[DisputeState, str], DisputeState] = {
    (DisputeState.RECEIVED, "validate"): DisputeState.VALIDATED,
    (DisputeState.RECEIVED, "reject"): DisputeState.REJECTED,
    (DisputeState.VALIDATED, "request_evidence"): DisputeState.EVIDENCE_PENDING,
    (DisputeState.VALIDATED, "start_investigation"): DisputeState.INVESTIGATION,
    (DisputeState.EVIDENCE_PENDING, "start_investigation"): DisputeState.INVESTIGATION,
    (DisputeState.INVESTIGATION, "propose_resolution"): DisputeState.RESOLUTION_PROPOSED,
    (DisputeState.RESOLUTION_PROPOSED, "accept_resolution"): DisputeState.RESOLVED,
    (DisputeState.RESOLUTION_PROPOSED, "reject_resolution"): DisputeState.REJECTED,
    (DisputeState.RESOLVED, "close"): DisputeState.CLOSED,
    (DisputeState.REJECTED, "close"): DisputeState.CLOSED,
}


class TransitionPolicy:
    TERMINAL_STATES = frozenset({DisputeState.CLOSED})

    def next_state(self, state: DisputeState, action: str) -> DisputeState:
        if state in self.TERMINAL_STATES:
            raise TerminalStateError("closed dispute cases cannot change")
        try:
            return TRANSITION_TABLE[(state, action)]
        except KeyError as exc:
            raise InvalidTransitionError(f"{action} is not valid from {state.value}") from exc


@dataclasses.dataclass(frozen=True)
class DisputeCase:
    dispute_id: DisputeId
    transaction_reference: TransactionReference
    amount: Money
    reason: DisputeReason
    case_type: str = "failed_debit_no_credit"
    state: DisputeState = DisputeState.RECEIVED
    version: CaseVersion = dataclasses.field(default_factory=CaseVersion)
    evidence: tuple[EvidenceItem, ...] = ()
    resolution: ResolutionDecision | None = None
    timeline: tuple[DomainEvent, ...] = ()

    def __post_init__(self) -> None:
        EligibilityPolicy().assert_eligible(self.reason, self.amount, self.case_type)

    @classmethod
    def open(
        cls,
        dispute_id: DisputeId,
        transaction_reference: TransactionReference,
        amount: Money,
        reason: DisputeReason,
        occurred_at: dt.datetime,
    ) -> DisputeCase:
        case = cls(dispute_id, transaction_reference, amount, reason)
        return case._record("case_received", case.state, {"reason": reason.value}, occurred_at)

    def validate(self, occurred_at: dt.datetime) -> DisputeCase:
        return self._transition("validate", "case_validated", {}, occurred_at)

    def reject(self, rationale: str, occurred_at: dt.datetime) -> DisputeCase:
        return self._transition("reject", "case_rejected", {"rationale": rationale}, occurred_at)

    def request_evidence(self, occurred_at: dt.datetime) -> DisputeCase:
        return self._transition(
            "request_evidence",
            "evidence_requested",
            {"missing": list(EvidenceCompletenessPolicy().missing_types(self.evidence))},
            occurred_at,
        )

    def submit_evidence(self, evidence_item: EvidenceItem, occurred_at: dt.datetime) -> DisputeCase:
        TransitionPolicy().next_state(self.state, "start_investigation" if self.state is DisputeState.EVIDENCE_PENDING else "request_evidence")
        if any(item.evidence_id == evidence_item.evidence_id for item in self.evidence):
            raise DisputeDomainError("duplicate evidence item")
        case = dataclasses.replace(self, evidence=(*self.evidence, evidence_item))
        target = (
            DisputeState.INVESTIGATION
            if EvidenceCompletenessPolicy().is_complete(case.evidence)
            else DisputeState.EVIDENCE_PENDING
        )
        return case._record(
            "evidence_submitted",
            target,
            {"evidence_id": evidence_item.evidence_id, "complete": target is DisputeState.INVESTIGATION},
            occurred_at,
        )

    def start_investigation(self, occurred_at: dt.datetime) -> DisputeCase:
        next_state = TransitionPolicy().next_state(self.state, "start_investigation")
        if not EvidenceCompletenessPolicy().is_complete(self.evidence):
            raise DisputeDomainError("evidence is incomplete")
        return self._record("investigation_started", next_state, {}, occurred_at)

    def propose_resolution(self, decision: ResolutionDecision, occurred_at: dt.datetime) -> DisputeCase:
        ResolutionPolicy().assert_decision_allowed(self, decision)
        next_state = TransitionPolicy().next_state(self.state, "propose_resolution")
        case = dataclasses.replace(self, resolution=decision)
        return case._record(
            "resolution_proposed",
            next_state,
            {"decision_id": decision.decision_id, "kind": decision.kind.value},
            occurred_at,
        )

    def accept_resolution(self, occurred_at: dt.datetime) -> DisputeCase:
        if self.resolution is None:
            raise DisputeDomainError("resolution decision is required")
        return self._transition("accept_resolution", "case_resolved", {}, occurred_at)

    def reject_resolution(self, rationale: str, occurred_at: dt.datetime) -> DisputeCase:
        if self.resolution is None:
            raise DisputeDomainError("resolution decision is required")
        return self._transition("reject_resolution", "case_rejected", {"rationale": rationale}, occurred_at)

    def close(self, occurred_at: dt.datetime) -> DisputeCase:
        return self._transition("close", "case_closed", {}, occurred_at)

    def _transition(
        self, action: str, event_type: str, payload: dict[str, Any], occurred_at: dt.datetime
    ) -> DisputeCase:
        return self._record(event_type, TransitionPolicy().next_state(self.state, action), payload, occurred_at)

    def _record(
        self, event_type: str, to_state: DisputeState, payload: dict[str, Any], occurred_at: dt.datetime
    ) -> DisputeCase:
        if occurred_at.tzinfo is None:
            raise ValueError("domain event time must be timezone-aware")
        next_version = self.version.next()
        event = DomainEvent(
            event_id=_event_id(self.dispute_id.value, next_version.value, event_type),
            dispute_id=self.dispute_id.value,
            event_type=event_type,
            from_state=self.state.value,
            to_state=to_state.value,
            case_version=next_version.value,
            occurred_at=occurred_at.isoformat(),
            payload=dict(payload),
        )
        return dataclasses.replace(
            self,
            state=to_state,
            version=next_version,
            timeline=(*self.timeline, event),
        )

    def replay(self) -> DisputeCase:
        rebuilt = dataclasses.replace(self, state=DisputeState.RECEIVED, version=CaseVersion(), timeline=())
        for event in self.timeline:
            rebuilt = dataclasses.replace(
                rebuilt,
                state=DisputeState(event.to_state),
                version=CaseVersion(event.case_version),
                timeline=(*rebuilt.timeline, event),
            )
        return rebuilt


def _event_id(dispute_id: str, version: int, event_type: str) -> str:
    digest = hashlib.sha256(f"{dispute_id}:{version}:{event_type}".encode("utf-8")).hexdigest()[:16]
    return f"EVT-{digest.upper()}"


class DisputeCaseRepositoryPort(Protocol):
    def get(self, dispute_id: DisputeId) -> DisputeCase | None: ...

    def find_by_transaction_reference(self, reference: TransactionReference) -> DisputeCase | None: ...

    def search(self, state: DisputeState | None = None) -> list[DisputeCase]: ...

    def save(self, case: DisputeCase, expected_version: CaseVersion | None = None) -> None: ...


class InMemoryDisputeCaseRepository:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}

    def get(self, dispute_id: DisputeId) -> DisputeCase | None:
        case = self._cases.get(dispute_id.value)
        return None if case is None else copy.deepcopy(case)

    def find_by_transaction_reference(self, reference: TransactionReference) -> DisputeCase | None:
        for case in self._cases.values():
            if case.transaction_reference == reference:
                return copy.deepcopy(case)
        return None

    def search(self, state: DisputeState | None = None) -> list[DisputeCase]:
        cases = sorted(self._cases.values(), key=lambda item: item.dispute_id.value)
        if state is not None:
            cases = [case for case in cases if case.state is state]
        return copy.deepcopy(cases)

    def save(self, case: DisputeCase, expected_version: CaseVersion | None = None) -> None:
        current = self._cases.get(case.dispute_id.value)
        expected = 0 if expected_version is None else expected_version.value
        if current is None:
            if expected != 0:
                raise OptimisticConcurrencyError("dispute case does not exist at expected version")
        elif current.version.value != expected:
            raise OptimisticConcurrencyError("dispute case version conflict")
        self._cases[case.dispute_id.value] = copy.deepcopy(case)


@dataclasses.dataclass(frozen=True)
class MutationCommand:
    principal: Principal
    idempotency_key: str
    correlation_id: str
    expected_version: CaseVersion | None


@dataclasses.dataclass(frozen=True)
class CreateDisputeCommand(MutationCommand):
    dispute_id: DisputeId
    transaction_reference: TransactionReference
    amount: Money
    reason: DisputeReason


@dataclasses.dataclass(frozen=True)
class SubmitEvidenceCommand(MutationCommand):
    dispute_id: DisputeId
    evidence: EvidenceItem


@dataclasses.dataclass(frozen=True)
class ValidateDisputeCommand(MutationCommand):
    dispute_id: DisputeId


@dataclasses.dataclass(frozen=True)
class StartInvestigationCommand(MutationCommand):
    dispute_id: DisputeId


@dataclasses.dataclass(frozen=True)
class ProposeResolutionCommand(MutationCommand):
    dispute_id: DisputeId
    decision: ResolutionDecision


@dataclasses.dataclass(frozen=True)
class AcceptResolutionCommand(MutationCommand):
    dispute_id: DisputeId


@dataclasses.dataclass(frozen=True)
class RejectResolutionCommand(MutationCommand):
    dispute_id: DisputeId
    rationale: str


@dataclasses.dataclass(frozen=True)
class CloseDisputeCommand(MutationCommand):
    dispute_id: DisputeId


@dataclasses.dataclass(frozen=True)
class DisputeQuery:
    principal: Principal
    correlation_id: str


@dataclasses.dataclass(frozen=True)
class GetDisputeQuery(DisputeQuery):
    dispute_id: DisputeId


@dataclasses.dataclass(frozen=True)
class SearchDisputesQuery(DisputeQuery):
    state: DisputeState | None = None


class InMemoryIdempotencyPort:
    def __init__(self) -> None:
        self._records: dict[str, tuple[str, dict[str, Any]]] = {}

    def replay_or_record(
        self, key: str, request_body: dict[str, Any], handler: Callable[[], dict[str, Any]]
    ) -> tuple[dict[str, Any], bool]:
        request_hash = hashlib.sha256(json.dumps(request_body, sort_keys=True).encode("utf-8")).hexdigest()
        row = self._records.get(key)
        if row is not None:
            if row[0] != request_hash:
                raise DisputeDomainError("idempotency key reused with different command")
            return copy.deepcopy(row[1]), True
        result = handler()
        self._records[key] = (request_hash, copy.deepcopy(result))
        return result, False


class DisputeApplicationService:
    PERMISSIONS = {
        "create": "dispute.create",
        "read": "dispute.read",
        "search": "dispute.search",
        "audit": "dispute.audit",
        "timeline": "dispute.timeline",
        "submit_evidence": "dispute.evidence.submit",
        "validate": "dispute.validate",
        "investigate": "dispute.investigate",
        "resolve": "dispute.resolve",
        "close": "dispute.close",
    }

    def __init__(
        self,
        repository: DisputeCaseRepositoryPort,
        authorizer: AuthorizationPort,
        idempotency: InMemoryIdempotencyPort,
        clock: Callable[[], dt.datetime],
    ) -> None:
        self.repository = repository
        self.authorizer = authorizer
        self.idempotency = idempotency
        self.clock = clock

    def create(self, command: CreateDisputeCommand) -> tuple[DisputeCase, bool]:
        self.authorizer.require(command.principal, self.PERMISSIONS["create"], "dispute:*")
        body = _command_body(command)

        def handler() -> dict[str, Any]:
            if self.repository.find_by_transaction_reference(command.transaction_reference) is not None:
                raise DuplicateDisputeError("duplicate dispute for transaction reference")
            case = DisputeCase.open(
                command.dispute_id,
                command.transaction_reference,
                command.amount,
                command.reason,
                self.clock(),
            )
            self.repository.save(case, CaseVersion(0))
            return _case_to_dict(case)

        payload, replayed = self.idempotency.replay_or_record(command.idempotency_key, body, handler)
        return _case_from_dict(payload), replayed

    def submit_evidence(self, command: SubmitEvidenceCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "submit_evidence", lambda case: case.submit_evidence(command.evidence, self.clock()))

    def validate(self, command: ValidateDisputeCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "validate", lambda case: case.validate(self.clock()))

    def start_investigation(self, command: StartInvestigationCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "investigate", lambda case: case.start_investigation(self.clock()))

    def propose_resolution(self, command: ProposeResolutionCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "resolve", lambda case: case.propose_resolution(command.decision, self.clock()))

    def accept_resolution(self, command: AcceptResolutionCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "resolve", lambda case: case.accept_resolution(self.clock()))

    def reject_resolution(self, command: RejectResolutionCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "resolve", lambda case: case.reject_resolution(command.rationale, self.clock()))

    def close(self, command: CloseDisputeCommand) -> tuple[DisputeCase, bool]:
        return self._mutate(command, "close", lambda case: case.close(self.clock()))

    def get(self, query: GetDisputeQuery) -> DisputeCase:
        self.authorizer.require(query.principal, self.PERMISSIONS["read"], query.dispute_id.value)
        case = self.repository.get(query.dispute_id)
        if case is None:
            raise KeyError(query.dispute_id.value)
        return case

    def search(self, query: SearchDisputesQuery) -> list[DisputeCase]:
        self.authorizer.require(query.principal, self.PERMISSIONS["search"], "dispute:*")
        return self.repository.search(query.state)

    def timeline(self, query: GetDisputeQuery) -> tuple[DomainEvent, ...]:
        self.authorizer.require(query.principal, self.PERMISSIONS["timeline"], query.dispute_id.value)
        return self.get(query).timeline

    def audit(self, query: GetDisputeQuery) -> dict[str, Any]:
        self.authorizer.require(query.principal, self.PERMISSIONS["audit"], query.dispute_id.value)
        case = self.get(query)
        event_hashes = [_event_hash(event) for event in case.timeline]
        return {
            "dispute_id": case.dispute_id.value,
            "version": case.version.value,
            "event_count": len(case.timeline),
            "event_hashes": event_hashes,
            "timeline_hash": hashlib.sha256("".join(event_hashes).encode("utf-8")).hexdigest(),
        }

    def _mutate(
        self,
        command: MutationCommand,
        permission_key: str,
        operation: Callable[[DisputeCase], DisputeCase],
    ) -> tuple[DisputeCase, bool]:
        dispute_id = getattr(command, "dispute_id")
        self.authorizer.require(command.principal, self.PERMISSIONS[permission_key], dispute_id.value)
        body = _command_body(command)

        def handler() -> dict[str, Any]:
            current = self.repository.get(dispute_id)
            if current is None:
                raise KeyError(dispute_id.value)
            expected = command.expected_version
            if expected is not None and current.version != expected:
                raise OptimisticConcurrencyError("dispute case version conflict")
            updated = operation(current)
            self.repository.save(updated, current.version)
            return _case_to_dict(updated)

        payload, replayed = self.idempotency.replay_or_record(command.idempotency_key, body, handler)
        return _case_from_dict(payload), replayed


def _command_body(command: MutationCommand) -> dict[str, Any]:
    return cast(dict[str, Any], _to_jsonable(dataclasses.asdict(command)))


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return [_to_jsonable(item) for item in sorted(value, key=str)]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _event_hash(event: DomainEvent) -> str:
    return hashlib.sha256(json.dumps(_to_jsonable(dataclasses.asdict(event)), sort_keys=True).encode()).hexdigest()


def _case_to_dict(case: DisputeCase) -> dict[str, Any]:
    return cast(dict[str, Any], _to_jsonable(dataclasses.asdict(case)))


def _case_from_dict(payload: dict[str, Any]) -> DisputeCase:
    evidence = tuple(
        EvidenceItem(
            evidence_id=str(item["evidence_id"]),
            evidence_type=str(item["evidence_type"]),
            source=str(item["source"]),
            summary=str(item["summary"]),
            observed_at=dt.datetime.fromisoformat(str(item["observed_at"])),
        )
        for item in payload.get("evidence", [])
    )
    resolution_payload = payload.get("resolution")
    resolution = None
    if isinstance(resolution_payload, dict):
        resolution = ResolutionDecision(
            decision_id=str(resolution_payload["decision_id"]),
            kind=ResolutionKind(str(resolution_payload["kind"])),
            amount=Money.of(str(resolution_payload["amount"]["amount"]), str(resolution_payload["amount"]["currency"])),
            rationale=str(resolution_payload["rationale"]),
            decided_by=str(resolution_payload["decided_by"]),
        )
    timeline = tuple(
        DomainEvent(
            event_id=str(item["event_id"]),
            dispute_id=str(item["dispute_id"]),
            event_type=str(item["event_type"]),
            from_state=str(item["from_state"]),
            to_state=str(item["to_state"]),
            case_version=int(item["case_version"]),
            occurred_at=str(item["occurred_at"]),
            payload=dict(item["payload"]),
        )
        for item in payload.get("timeline", [])
    )
    return DisputeCase(
        dispute_id=DisputeId(str(payload["dispute_id"]["value"])),
        transaction_reference=TransactionReference(str(payload["transaction_reference"]["value"])),
        amount=Money.of(str(payload["amount"]["amount"]), str(payload["amount"]["currency"])),
        reason=DisputeReason(str(payload["reason"])),
        case_type=str(payload["case_type"]),
        state=DisputeState(str(payload["state"])),
        version=CaseVersion(int(payload["version"]["value"])),
        evidence=evidence,
        resolution=resolution,
        timeline=timeline,
    )
