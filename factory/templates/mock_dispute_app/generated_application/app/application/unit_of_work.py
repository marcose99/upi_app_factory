from __future__ import annotations

from types import TracebackType
from typing import Protocol

from .ports import DisputeRepository, IdempotencyStore, Outbox


class UnitOfWork(Protocol):
    disputes: DisputeRepository
    idempotency: IdempotencyStore
    outbox: Outbox

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
