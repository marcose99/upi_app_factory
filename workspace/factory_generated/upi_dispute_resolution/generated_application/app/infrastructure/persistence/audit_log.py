from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


class SqliteAuditLog:
    GENESIS = "0" * 64

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def append(self, actor_id: str, action: str, target: str, payload: dict[str, Any]) -> str:
        previous = self.connection.execute(
            "select record_hash from audit_records order by sequence desc limit 1"
        ).fetchone()
        previous_hash = self.GENESIS if previous is None else str(previous[0])
        occurred_at_utc = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        body = "|".join([occurred_at_utc, actor_id, action, target, payload_json, previous_hash])
        record_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.connection.execute(
            """
            insert into audit_records(
                occurred_at_utc, actor_id, action, target, payload_json, previous_hash, record_hash
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (occurred_at_utc, actor_id, action, target, payload_json, previous_hash, record_hash),
        )
        return record_hash

    def verify(self) -> bool:
        previous_hash = self.GENESIS
        rows = self.connection.execute(
            "select occurred_at_utc, actor_id, action, target, payload_json, previous_hash, record_hash "
            "from audit_records order by sequence"
        ).fetchall()
        for row in rows:
            body = "|".join([str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), previous_hash])
            expected = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if str(row[5]) != previous_hash or str(row[6]) != expected:
                return False
            previous_hash = str(row[6])
        return True
