from __future__ import annotations

from dataclasses import asdict

from app.upi_failed_debit_dispute.domain.aggregates.dispute_case import DisputeCase


class DisputeApplicationService:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}
        self._idempotency: dict[str, str] = {}

    def create(self, payload: dict[str, str], idempotency_key: str) -> dict[str, object]:
        if idempotency_key in self._idempotency:
            return self.get(self._idempotency[idempotency_key])
        case = DisputeCase(
            dispute_id=payload["dispute_id"],
            transaction_reference=payload["transaction_reference"],
            amount=payload["amount"],
            reason=payload["reason"],
        )
        self._cases[case.dispute_id] = case
        self._idempotency[idempotency_key] = case.dispute_id
        return asdict(case)

    def get(self, dispute_id: str) -> dict[str, object]:
        return asdict(self._cases[dispute_id])

    def list(self) -> list[dict[str, object]]:
        return [asdict(case) for case in self._cases.values()]

    def action(self, dispute_id: str, target: str, event: str) -> dict[str, object]:
        case = self._cases[dispute_id]
        case.transition(target, event)
        return asdict(case)
