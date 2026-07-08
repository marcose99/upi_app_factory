from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from .idempotency_store import SqliteIdempotencyStore
from .outbox import SqliteOutbox
from .repositories import SqliteDisputeRepository


SCHEMA = """
create table if not exists disputes(
  dispute_id text primary key,
  transaction_ref text not null,
  customer_upi text not null,
  reason text not null,
  state text not null
);
create table if not exists idempotency_keys(key text primary key, result text not null);
create table if not exists outbox(
  id integer primary key autoincrement,
  event_type text not null,
  aggregate_id text not null,
  payload_json text not null,
  dispatched integer not null default 0
);
"""


class SqliteUnitOfWork:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.connection: sqlite3.Connection | None = None

    def __enter__(self) -> SqliteUnitOfWork:
        self.connection = sqlite3.connect(self.database_path)
        self.connection.executescript(SCHEMA)
        self.disputes = SqliteDisputeRepository(self.connection)
        self.idempotency = SqliteIdempotencyStore(self.connection)
        self.outbox = SqliteOutbox(self.connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.connection is None:
            return
        if exc is not None:
            self.connection.rollback()
        self.connection.close()

    def commit(self) -> None:
        if self.connection is None:
            raise RuntimeError("Unit of work is not active")
        self.connection.commit()
