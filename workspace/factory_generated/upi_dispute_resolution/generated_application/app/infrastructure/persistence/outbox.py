from __future__ import annotations

import json
import sqlite3
from typing import cast

from generated_application.app.domain.domain_events import DomainEvent, portable_event_envelope
from generated_application.app.observability.tracing import event_trace_context


class SqliteOutbox:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def enqueue(self, event: DomainEvent, *, trace_id: str = "local-trace") -> str:
        trace_context = event_trace_context()
        if trace_context.get("correlation_id") == "local":
            trace_context["correlation_id"] = trace_id
        envelope = portable_event_envelope(
            event,
            trace_id=trace_context["trace_id"],
            trace_context=trace_context,
        )
        self.connection.execute(
            """
            insert into outbox(
                message_id, event_type, aggregate_id, aggregate_version,
                envelope_json, payload_sha256, dispatched
            ) values (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                envelope.message_id,
                envelope.event_type,
                envelope.aggregate_id,
                envelope.aggregate_version,
                envelope.to_json(),
                envelope.payload_sha256,
            ),
        )
        return cast(str, envelope.message_id)

    def pending(self) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """
            select message_id, event_type, aggregate_id, aggregate_version, envelope_json
            from outbox
            where dispatched = 0
            order by id
            """
        ).fetchall()
        return [
            {
                "message_id": str(row[0]),
                "event_type": str(row[1]),
                "aggregate_id": str(row[2]),
                "aggregate_version": int(row[3]),
                "envelope": json.loads(str(row[4])),
            }
            for row in rows
        ]

    def mark_dispatched(self, message_id: str) -> None:
        self.connection.execute(
            """
            update outbox
            set dispatched = 1, dispatched_at_utc = datetime('now')
            where message_id = ?
            """,
            (message_id,),
        )
