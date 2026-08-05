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

    def append(
        self,
        actor_id: str,
        actor_role: str,
        action: str | None = None,
        target: str | dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        if isinstance(target, dict) and payload is None and action is not None:
            action_name = actor_role
            target_name = action
            payload_value = target
            actor_role = "unknown"
        else:
            if action is None or not isinstance(target, str) or payload is None:
                raise TypeError("append requires actor_id, actor_role, action, target, and payload")
            action_name = action
            target_name = target
            payload_value = payload
        previous = self.connection.execute(
            "select record_hash from audit_records order by sequence desc limit 1"
        ).fetchone()
        previous_hash = self.GENESIS if previous is None else str(previous[0])
        occurred_at_utc = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload_value, sort_keys=True, separators=(",", ":"))
        body = self._hash_body(
            occurred_at_utc=occurred_at_utc,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action_name,
            target=target_name,
            payload_json=payload_json,
            previous_hash=previous_hash,
        )
        record_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.connection.execute(
            """
            insert into audit_records(
                occurred_at_utc, actor_id, actor_role, action, target, payload_json, previous_hash, record_hash
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurred_at_utc,
                actor_id,
                actor_role,
                action_name,
                target_name,
                payload_json,
                previous_hash,
                record_hash,
            ),
        )
        return record_hash

    def verify(self) -> bool:
        previous_hash = self.GENESIS
        rows = self.connection.execute(
            "select occurred_at_utc, actor_id, actor_role, action, target, payload_json, previous_hash, record_hash "
            "from audit_records order by sequence"
        ).fetchall()
        for row in rows:
            expected = hashlib.sha256(
                self._hash_body(
                    occurred_at_utc=str(row[0]),
                    actor_id=str(row[1]),
                    actor_role=str(row[2]),
                    action=str(row[3]),
                    target=str(row[4]),
                    payload_json=str(row[5]),
                    previous_hash=previous_hash,
                ).encode("utf-8")
            ).hexdigest()
            if str(row[6]) != previous_hash:
                return False
            if str(row[7]) != expected:
                legacy = hashlib.sha256(
                    "|".join(
                        [
                            str(row[0]),
                            str(row[1]),
                            str(row[3]),
                            str(row[4]),
                            str(row[5]),
                            previous_hash,
                        ]
                    ).encode("utf-8")
                ).hexdigest()
                if not (str(row[2]) == "unknown" and str(row[7]) == legacy):
                    return False
            previous_hash = str(row[7])
        return True

    @staticmethod
    def _hash_body(
        *,
        occurred_at_utc: str,
        actor_id: str,
        actor_role: str,
        action: str,
        target: str,
        payload_json: str,
        previous_hash: str,
    ) -> str:
        return "|".join(
            [occurred_at_utc, actor_id, actor_role, action, target, payload_json, previous_hash]
        )
