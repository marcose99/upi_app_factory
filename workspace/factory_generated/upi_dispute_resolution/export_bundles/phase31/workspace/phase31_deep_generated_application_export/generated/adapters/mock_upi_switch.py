from __future__ import annotations

from typing import Any


def list_failed_transactions() -> list[dict[str, Any]]:
    return [
        {
            "transaction_id": "SYN-UPI-TXN-0001",
            "customer_reference": "SYN-CUST-001",
            "amount_paise": 125000,
            "currency": "INR",
            "failure_reason": "Synthetic timeout after debit observation",
            "observed_at_utc": "2026-07-04T10:00:00+00:00",
        },
        {
            "transaction_id": "SYN-UPI-TXN-0002",
            "customer_reference": "SYN-CUST-002",
            "amount_paise": 49900,
            "currency": "INR",
            "failure_reason": "Synthetic beneficiary credit status unknown",
            "observed_at_utc": "2026-07-04T10:05:00+00:00",
        },
    ]


def get_failed_transaction(transaction_id: str) -> dict[str, Any] | None:
    for event in list_failed_transactions():
        if event["transaction_id"] == transaction_id:
            return event
    return None
