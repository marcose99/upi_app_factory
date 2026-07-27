from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateDisputeCommand:
    transaction_ref: str
    customer_upi: str
    reason: str
    idempotency_key: str
    correlation_id: str
    owner_subject: str = "local-system"
