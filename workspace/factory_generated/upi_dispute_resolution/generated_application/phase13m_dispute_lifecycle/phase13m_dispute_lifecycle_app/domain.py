from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DisputeStatus(str, Enum):
    INTAKE_ACCEPTED = "INTAKE_ACCEPTED"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    INVESTIGATION_RESPONDED = "INVESTIGATION_RESPONDED"
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"
    RESOLVED = "RESOLVED"


class ResolutionOutcome(str, Enum):
    CUSTOMER_CREDIT_RECOMMENDED = "CUSTOMER_CREDIT_RECOMMENDED"
    MERCHANT_DEFENSE_ACCEPTED = "MERCHANT_DEFENSE_ACCEPTED"


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    details: dict[str, Any]
    created_at_utc: str


@dataclass
class DisputeCase:
    case_id: str
    transaction_id: str
    payer_vpa: str
    payee_vpa: str
    amount_paise: int
    status: DisputeStatus
    evidence_refs: list[str]
    mock_investigation_reference: str | None = None
    resolution_outcome: ResolutionOutcome | None = None
    audit_trail: list[AuditEvent] = field(default_factory=list)

    def add_event(self, event_type: str, details: dict[str, Any]) -> None:
        self.audit_trail.append(
            AuditEvent(
                event_type=event_type,
                details=details,
                created_at_utc=utc_now_iso(),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "transaction_id": self.transaction_id,
            "payer_vpa": self.payer_vpa,
            "payee_vpa": self.payee_vpa,
            "amount_paise": self.amount_paise,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
            "mock_investigation_reference": self.mock_investigation_reference,
            "resolution_outcome": (
                None
                if self.resolution_outcome is None
                else self.resolution_outcome.value
            ),
            "audit_trail": [
                {
                    "event_type": event.event_type,
                    "details": dict(event.details),
                    "created_at_utc": event.created_at_utc,
                }
                for event in self.audit_trail
            ],
            "boundary_statement": (
                "Primary UPI dispute lifecycle logic is local and runnable; "
                "external banks, rails, NPCI-style, RBI-style, upstream, and "
                "downstream ecosystem interfaces are simulated mocks only."
            ),
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
