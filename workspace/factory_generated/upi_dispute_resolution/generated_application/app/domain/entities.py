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
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"


ALLOWED_TRANSITIONS: dict[DisputeState, set[DisputeState]] = {
    DisputeState.RECEIVED: {DisputeState.VALIDATED, DisputeState.REJECTED},
    DisputeState.VALIDATED: {DisputeState.EVIDENCE_PENDING, DisputeState.UNDER_REVIEW},
    DisputeState.EVIDENCE_PENDING: {DisputeState.UNDER_REVIEW, DisputeState.REJECTED},
    DisputeState.UNDER_REVIEW: {DisputeState.RESOLVED, DisputeState.REJECTED},
    DisputeState.RESOLVED: {DisputeState.CLOSED},
    DisputeState.REJECTED: {DisputeState.CLOSED},
    DisputeState.CLOSED: set(),
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
