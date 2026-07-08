from __future__ import annotations

import sqlite3


class SqliteIdempotencyStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, key: str) -> str | None:
        row = self.connection.execute("select result from idempotency_keys where key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def put(self, key: str, value: str) -> None:
        self.connection.execute(
            "insert or ignore into idempotency_keys(key, result) values (?, ?)",
            (key, value),
        )
