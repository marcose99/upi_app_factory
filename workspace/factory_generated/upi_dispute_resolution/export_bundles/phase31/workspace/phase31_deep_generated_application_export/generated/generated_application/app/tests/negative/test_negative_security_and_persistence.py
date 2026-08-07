from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from generated_application.app.interfaces.api.main import app
from generated_application.app.security.identity import local_principal


def test_protected_api_rejects_unauthenticated_dispute_access() -> None:
    schema = app.openapi()
    protected = {
        ("/disputes", "post"),
        ("/disputes", "get"),
        ("/disputes/{dispute_id}", "get"),
    }
    for path, method in protected:
        assert schema["paths"][path][method]["security"]
    with pytest.raises(HTTPException) as exc:
        local_principal(authorization=None, subject=None)
    assert exc.value.status_code == 401


def test_local_sqlite_storage_does_not_contain_raw_upi_identifier(tmp_path: Path) -> None:
    database = tmp_path / "minimized.sqlite3"
    raw_upi = "rawcustomer@example"
    service = DisputeService(SqliteUnitOfWork(database))
    dispute_id = service.create_dispute(
        CreateDisputeCommand(
            transaction_ref="NEGATIVE002",
            customer_upi=raw_upi,
            reason="local data minimization coverage",
            idempotency_key="negative-minimize-1",
            correlation_id="corr-negative",
            owner_subject="client-negative",
        )
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "select customer_upi, customer_upi_masked from disputes where dispute_id = ?",
            (dispute_id,),
        ).fetchone()
        assert row is not None

    persisted_digest, persisted_mask = str(row[0]), str(row[1])
    assert raw_upi not in database.read_text(encoding="latin-1", errors="ignore")
    assert persisted_digest.startswith("sha256:")
    assert persisted_mask == "[masked:ra***@example]"
