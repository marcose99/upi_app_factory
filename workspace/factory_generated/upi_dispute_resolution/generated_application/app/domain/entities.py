from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .domain_events import DomainEvent, dispute_event
from .exceptions import InvalidStateTransition
from .value_objects import DisputeId, UpiTransactionRef


class DisputeState(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    EVIDENCE_PENDING = "evidence_pending"
    INVESTIGATION = "investigation"
    RESOLUTION_PROPOSED = "resolution_proposed"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"


class FailedDebitCaseState(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    INVESTIGATING = "investigating"
    AWAITING_EVIDENCE = "awaiting_evidence"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    DECISION_RECORDED = "decision_recorded"
    RESOLVED = "resolved"
    CLOSED = "closed"
    QUARANTINED = "quarantined"


ALLOWED_TRANSITIONS: dict[DisputeState, set[DisputeState]] = {
    DisputeState.RECEIVED: {DisputeState.VALIDATED, DisputeState.REJECTED},
    DisputeState.VALIDATED: {
        DisputeState.EVIDENCE_PENDING,
        DisputeState.INVESTIGATION,
        DisputeState.UNDER_REVIEW,
    },
    DisputeState.EVIDENCE_PENDING: {
        DisputeState.INVESTIGATION,
        DisputeState.UNDER_REVIEW,
        DisputeState.REJECTED,
    },
    DisputeState.INVESTIGATION: {
        DisputeState.RESOLUTION_PROPOSED,
        DisputeState.RESOLVED,
        DisputeState.REJECTED,
    },
    DisputeState.RESOLUTION_PROPOSED: {DisputeState.RESOLVED, DisputeState.REJECTED},
    DisputeState.UNDER_REVIEW: {DisputeState.RESOLVED, DisputeState.REJECTED},
    DisputeState.RESOLVED: {DisputeState.CLOSED},
    DisputeState.REJECTED: {DisputeState.CLOSED},
    DisputeState.CLOSED: set(),
}


FAILED_DEBIT_ALLOWED_TRANSITIONS: dict[FailedDebitCaseState, set[FailedDebitCaseState]] = {
    FailedDebitCaseState.RECEIVED: {FailedDebitCaseState.VALIDATED},
    FailedDebitCaseState.VALIDATED: {
        FailedDebitCaseState.INVESTIGATING,
        FailedDebitCaseState.AWAITING_EVIDENCE,
    },
    FailedDebitCaseState.INVESTIGATING: {
        FailedDebitCaseState.AWAITING_EVIDENCE,
        FailedDebitCaseState.AWAITING_HUMAN_REVIEW,
        FailedDebitCaseState.DECISION_RECORDED,
        FailedDebitCaseState.QUARANTINED,
    },
    FailedDebitCaseState.AWAITING_EVIDENCE: {
        FailedDebitCaseState.VALIDATED,
        FailedDebitCaseState.INVESTIGATING,
        FailedDebitCaseState.AWAITING_HUMAN_REVIEW,
        FailedDebitCaseState.QUARANTINED,
    },
    FailedDebitCaseState.AWAITING_HUMAN_REVIEW: {
        FailedDebitCaseState.DECISION_RECORDED,
        FailedDebitCaseState.QUARANTINED,
    },
    FailedDebitCaseState.DECISION_RECORDED: {
        FailedDebitCaseState.RESOLVED,
        FailedDebitCaseState.AWAITING_EVIDENCE,
        FailedDebitCaseState.QUARANTINED,
    },
    FailedDebitCaseState.RESOLVED: {
        FailedDebitCaseState.CLOSED,
        FailedDebitCaseState.QUARANTINED,
    },
    FailedDebitCaseState.CLOSED: set(),
    FailedDebitCaseState.QUARANTINED: set(),
}


@dataclass
class Dispute:
    dispute_id: DisputeId
    transaction_ref: UpiTransactionRef
    customer_upi: str
    reason: str
    owner_subject: str = "local-system"
    state: DisputeState = DisputeState.RECEIVED
    version: int = 0
    audit_link_hash: str | None = None
    audit_events: list[DomainEvent] = field(default_factory=list)

    def transition_to(self, next_state: DisputeState, actor: str) -> None:
        if next_state not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidStateTransition(f"{self.state.value} cannot transition to {next_state.value}")
        previous = self.state
        self.state = next_state
        self.version += 1
        self.audit_events.append(
            dispute_event(
                "dispute.state_changed",
                self.dispute_id.value,
                self.version,
                {"from": previous.value, "to": next_state.value, "actor": actor},
            )
        )


def ensure_failed_debit_transition(current_state: str, next_state: str) -> None:
    if current_state == next_state:
        return
    try:
        current = FailedDebitCaseState(current_state)
        target = FailedDebitCaseState(next_state)
    except ValueError as exc:
        raise InvalidStateTransition(
            f"unsupported failed-debit state transition {current_state} -> {next_state}"
        ) from exc
    if target not in FAILED_DEBIT_ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(
            f"{current.value} cannot transition to {target.value}"
        )
