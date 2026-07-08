from __future__ import annotations

from typing import Protocol

from generated_application.app.domain.entities import Dispute


class DisputeRepository(Protocol):
    def add(self, dispute: Dispute) -> None: ...
    def get(self, dispute_id: str) -> Dispute | None: ...


class IdempotencyStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def put(self, key: str, value: str) -> None: ...


class Outbox(Protocol):
    def enqueue(self, event_type: str, aggregate_id: str, payload: dict[str, str]) -> None: ...
