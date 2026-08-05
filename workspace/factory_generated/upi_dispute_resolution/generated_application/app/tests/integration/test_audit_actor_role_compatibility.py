from __future__ import annotations

import sqlite3
from pathlib import Path

from generated_application.app.infrastructure.persistence.audit_log import SqliteAuditLog
from generated_application.app.infrastructure.persistence.migrations import apply_migrations


def test_audit_log_supports_actor_role_and_legacy_append_signatures(tmp_path: Path) -> None:
    database = tmp_path / "audit.sqlite3"
    connection = sqlite3.connect(database)
    try:
        apply_migrations(connection)
        audit = SqliteAuditLog(connection)

        first_hash = audit.append(
            "application_service",
            "system",
            "dispute.create",
            "DSP-1",
            {"state": "received"},
        )
        second_hash = audit.append(
            "legacy_actor",
            "dispute.update",
            "DSP-1",
            {"state": "validated"},
        )
        connection.commit()

        rows = connection.execute(
            "select actor_id, actor_role, action, target, record_hash from audit_records order by sequence"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        ("application_service", "system", "dispute.create", "DSP-1", first_hash),
        ("legacy_actor", "unknown", "dispute.update", "DSP-1", second_hash),
    ]

    verification_connection = sqlite3.connect(database)
    try:
        verifier = SqliteAuditLog(verification_connection)
        assert verifier.verify() is True
    finally:
        verification_connection.close()
