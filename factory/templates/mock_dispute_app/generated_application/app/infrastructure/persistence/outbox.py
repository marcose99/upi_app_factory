from __future__ import annotations

import json
import sqlite3


class SqliteOutbox:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def enqueue(self, event_type: str, aggregate_id: str, payload: dict[str, str]) -> None:
        self.connection.execute(
            "insert into outbox(event_type, aggregate_id, payload_json) values (?, ?, ?)",
            (event_type, aggregate_id, json.dumps(payload, sort_keys=True)),
        )
