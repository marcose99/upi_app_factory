from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from .audit_log import SqliteAuditLog
from .idempotency_store import SqliteIdempotencyStore
from .inbox import SqliteInbox
from .migrations import apply_migrations
from .outbox import SqliteOutbox
from .repositories import SqliteDisputeRepository, SqliteFailedDebitRepository


class SqliteUnitOfWork:
    _migrated_paths: set[Path] = set()

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.connection: sqlite3.Connection | None = None
        self._committed = False

    def __enter__(self) -> SqliteUnitOfWork:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path, timeout=5.0, isolation_level=None)
        self.connection.execute("pragma busy_timeout = 5000")
        self.connection.execute("pragma foreign_keys = on")
        journal_mode = self.connection.execute("pragma journal_mode = wal").fetchone()
        if journal_mode is None or str(journal_mode[0]).lower() not in {"wal", "memory"}:
            raise RuntimeError("SQLite WAL journal mode could not be enabled for local review")
        if self.database_path not in self._migrated_paths:
            apply_migrations(self.connection)
            self.connection.commit()
            self._migrated_paths.add(self.database_path)
        else:
            rows = self.connection.execute("select 1 from schema_migrations limit 1").fetchone()
            if rows is None:
                apply_migrations(self.connection)
                self.connection.commit()
        self.connection.commit()
        self.connection.execute("begin immediate")
        self.disputes = SqliteDisputeRepository(self.connection)
        self.failed_debit = SqliteFailedDebitRepository(self.connection)
        self.idempotency = SqliteIdempotencyStore(self.connection)
        self.outbox = SqliteOutbox(self.connection)
        self.audit = SqliteAuditLog(self.connection)
        self.inbox = SqliteInbox(self.connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.connection is None:
            return
        if exc is not None or not self._committed:
            self.connection.rollback()
        self.connection.close()
        self.connection = None
        self._committed = False

    def commit(self) -> None:
        if self.connection is None:
            raise RuntimeError("Unit of work is not active")
        self.connection.commit()
        self._committed = True
