from __future__ import annotations

from typing import Protocol

from .models import DisputeRecord, DisputeStatus, EcosystemDecision


class DisputeRepositoryPort(Protocol):
    def add(
        self,
        record: DisputeRecord,
        *,
        request_fingerprint: str | None = None,
    ) -> DisputeRecord: ...

    def get_by_client_request_id(self, client_request_id: str) -> DisputeRecord: ...

    def get_request_fingerprint(self, client_request_id: str) -> str | None: ...

    def get(self, dispute_id: str) -> DisputeRecord: ...

    def list_all(self) -> list[DisputeRecord]: ...

    def update_status(
        self,
        *,
        dispute_id: str,
        status: DisputeStatus,
        updated_at_utc: str,
        note: str,
    ) -> DisputeRecord: ...


class AuditLogPort(Protocol):
    def record(
        self,
        *,
        event_type: str,
        actor: str,
        details: dict[str, object],
        dispute_id: str | None = None,
    ) -> object: ...


class MockEcosystemPort(Protocol):
    def decide(self, record: DisputeRecord) -> tuple[EcosystemDecision, str, list[str]]: ...


class UnitOfWorkPort(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
