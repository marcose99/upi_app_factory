from __future__ import annotations

from types import TracebackType
from typing import Protocol

from .ports import AuditLog, DisputeRepository, FailedDebitRepository, IdempotencyStore, Inbox, Outbox


class UnitOfWork(Protocol):
    disputes: DisputeRepository
    failed_debit: FailedDebitRepository
    idempotency: IdempotencyStore
    outbox: Outbox
    audit: AuditLog
    inbox: Inbox

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
