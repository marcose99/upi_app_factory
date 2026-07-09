from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import DisputeCreate, DisputeType


@dataclass(frozen=True)
class SubmitDisputeCommand:
    client_request_id: str
    dispute_type: DisputeType
    transaction_reference: str
    customer_upi_id: str
    amount_paise: int
    description: str
    evidence: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: DisputeCreate) -> SubmitDisputeCommand:
        return cls(
            client_request_id=payload.client_request_id,
            dispute_type=payload.dispute_type,
            transaction_reference=payload.transaction_reference,
            customer_upi_id=payload.customer_upi_id,
            amount_paise=payload.amount_paise,
            description=payload.description,
            evidence=payload.evidence,
        )


@dataclass(frozen=True)
class GetDisputeQuery:
    dispute_id: str


@dataclass(frozen=True)
class ListDisputesQuery:
    sort_order: str = "created_at_utc_ascending"


@dataclass(frozen=True)
class RunMockEcosystemCheckCommand:
    dispute_id: str
