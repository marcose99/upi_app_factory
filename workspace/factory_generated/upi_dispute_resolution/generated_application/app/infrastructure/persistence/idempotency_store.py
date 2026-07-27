from __future__ import annotations

import sqlite3


class SqliteIdempotencyStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, key: str) -> tuple[str, str] | None:
        row = self.connection.execute(
            "select request_fingerprint, result from idempotency_keys where key = ?",
            (key,),
        ).fetchone()
        return None if row is None else (str(row[0]), str(row[1]))

    def put(self, key: str, request_fingerprint: str, value: str) -> None:
        replayed = self.reserve(key, request_fingerprint)
        if replayed is None:
            self.finalize(key, request_fingerprint, value)

    def reserve(self, key: str, request_fingerprint: str) -> tuple[str, str] | None:
        cursor = self.connection.execute(
            """
            insert into idempotency_keys(key, request_fingerprint, result)
            values (?, ?, '')
            on conflict(key) do nothing
            """,
            (key, request_fingerprint),
        )
        if cursor.rowcount == 1:
            return None
        return self.get(key)

    def finalize(self, key: str, request_fingerprint: str, value: str) -> None:
        self.connection.execute(
            """
            update idempotency_keys
            set result = ?
            where key = ? and request_fingerprint = ? and result = ''
            """,
            (value, key, request_fingerprint),
        )
        updated = self.connection.total_changes
        row = self.connection.execute(
            "select changes()",
        ).fetchone()
        if row is None or int(row[0]) != 1:
            raise RuntimeError("idempotency reservation could not be finalized")
        if updated < 0:
            raise RuntimeError("sqlite total changes counter unavailable")
