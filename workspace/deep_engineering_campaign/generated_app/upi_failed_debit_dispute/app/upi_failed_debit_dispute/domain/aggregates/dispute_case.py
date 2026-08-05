from __future__ import annotations

from dataclasses import dataclass, field

from app.upi_failed_debit_dispute.domain.state_machines.dispute_lifecycle import TRANSITION_TABLE


class DomainError(RuntimeError):
    pass


@dataclass
class DisputeCase:
    dispute_id: str
    transaction_reference: str
    amount: str
    reason: str
    state: str = "received"
    version: int = 1
    evidence: list[str] = field(default_factory=list)
    timeline: list[str] = field(default_factory=lambda: ["case_received"])

    def transition(self, target: str, event: str) -> None:
        if target not in TRANSITION_TABLE[self.state]:
            raise DomainError(f"invalid transition {self.state} -> {target}")
        self.state = target
        self.version += 1
        self.timeline.append(event)
