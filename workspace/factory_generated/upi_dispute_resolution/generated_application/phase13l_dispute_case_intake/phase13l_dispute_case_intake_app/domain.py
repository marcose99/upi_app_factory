from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PaymentRail(str, Enum):
    UPI = "UPI"


class DisputeCategory(str, Enum):
    FAILED_TRANSACTION = "FAILED_TRANSACTION"
    UNAUTHORIZED_TRANSACTION = "UNAUTHORIZED_TRANSACTION"
    DUPLICATE_DEBIT = "DUPLICATE_DEBIT"
    GOODS_OR_SERVICE_NOT_RECEIVED = "GOODS_OR_SERVICE_NOT_RECEIVED"


class DisputeStatus(str, Enum):
    INTAKE_ACCEPTED = "INTAKE_ACCEPTED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"


@dataclass(frozen=True)
class DisputeCase:
    case_id: str
    transaction_id: str
    payer_vpa: str
    payee_vpa: str
    amount_paise: int
    rail: PaymentRail
    category: DisputeCategory
    status: DisputeStatus
    mock_ecosystem_reference: str
    evidence_refs: tuple[str, ...]
    created_at_utc: str
    boundary_statement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "transaction_id": self.transaction_id,
            "payer_vpa": self.payer_vpa,
            "payee_vpa": self.payee_vpa,
            "amount_paise": self.amount_paise,
            "rail": self.rail.value,
            "category": self.category.value,
            "status": self.status.value,
            "mock_ecosystem_reference": self.mock_ecosystem_reference,
            "evidence_refs": list(self.evidence_refs),
            "created_at_utc": self.created_at_utc,
            "boundary_statement": self.boundary_statement,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
