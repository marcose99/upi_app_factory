from __future__ import annotations

from typing import Any


def get_ledger_observation(transaction_id: str) -> dict[str, Any]:
    return {
        "source_system": "mock_core_banking",
        "transaction_id": transaction_id,
        "observation": (
            "Synthetic ledger observation: debit seen and beneficiary "
            "credit confirmation unavailable in mock evidence."
        ),
        "observed_at_utc": "2026-07-04T10:10:00+00:00",
    }
