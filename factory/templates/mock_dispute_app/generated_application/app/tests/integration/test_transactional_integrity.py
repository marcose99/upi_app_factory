from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
from generated_application.app.domain.exceptions import DuplicateBusinessSubmissionError, IdempotencyConflictError
from generated_application.app.domain.entities import Dispute
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork


def test_use_case_persists_aggregate_audit_and_outbox_atomically(tmp_path: Path) -> None:
    database = tmp_path / "app.sqlite3"

    dispute_id = DisputeService(SqliteUnitOfWork(database)).create_dispute(
        CreateDisputeCommand(
            transaction_ref="UPI12345",
            customer_upi="customer@example",
            reason="failed debit",
            idempotency_key="idem-1",
            correlation_id="corr-1",
            owner_subject="client-1",
        )
    )

    with sqlite3.connect(database) as connection:
        dispute = connection.execute(
            "select version, audit_link_hash, owner_subject from disputes where dispute_id = ?",
            (dispute_id,),
        ).fetchone()
        audit = connection.execute("select record_hash from audit_records").fetchone()
        outbox = connection.execute("select envelope_json from outbox").fetchone()

    assert dispute[0] == 1
    assert dispute[1] == audit[0]
    assert dispute[2] == "client-1"
    assert audit[0] in outbox[0]

    listed = DisputeService(SqliteUnitOfWork(database)).list_disputes(limit=10, cursor=0)
    assert [item.dispute_id.value for item in listed] == [dispute_id]
    assert listed[0].owner_subject == "client-1"


def test_idempotency_key_replay_is_bound_to_payload_and_owner(tmp_path: Path) -> None:
    database = tmp_path / "idempotency.sqlite3"
    service = DisputeService(SqliteUnitOfWork(database))
    command = CreateDisputeCommand(
        transaction_ref="UPI12345",
        customer_upi="customer@example",
        reason="failed debit",
        idempotency_key="idem-payload-bound",
        correlation_id="corr-1",
        owner_subject="client-1",
    )

    dispute_id = service.create_dispute(command)
    assert service.create_dispute(command) == dispute_id

    with pytest.raises(IdempotencyConflictError):
        service.create_dispute(
            CreateDisputeCommand(
                transaction_ref="UPI99999",
                customer_upi="customer@example",
                reason="different dispute",
                idempotency_key="idem-payload-bound",
                correlation_id="corr-2",
                owner_subject="client-1",
            )
        )

    with pytest.raises(IdempotencyConflictError):
        service.create_dispute(
            CreateDisputeCommand(
                transaction_ref="UPI12345",
                customer_upi="customer@example",
                reason="failed debit",
                idempotency_key="idem-payload-bound",
                correlation_id="corr-3",
                owner_subject="client-2",
            )
        )


def test_different_idempotency_key_cannot_duplicate_business_submission(tmp_path: Path) -> None:
    database = tmp_path / "business-duplicate.sqlite3"
    service = DisputeService(SqliteUnitOfWork(database))

    service.create_dispute(
        CreateDisputeCommand(
            transaction_ref="UPI12345",
            customer_upi="customer@example",
            reason="failed debit",
            idempotency_key="idem-business-1",
            correlation_id="corr-1",
            owner_subject="client-1",
        )
    )

    with pytest.raises(DuplicateBusinessSubmissionError):
        service.create_dispute(
            CreateDisputeCommand(
                transaction_ref="UPI12345",
                customer_upi="customer@example",
                reason="failed debit",
                idempotency_key="idem-business-2",
                correlation_id="corr-2",
                owner_subject="client-1",
            )
        )

    with sqlite3.connect(database) as connection:
        assert connection.execute("select count(*) from disputes").fetchone()[0] == 1
        assert connection.execute("select count(*) from idempotency_keys").fetchone()[0] == 1


def test_uncommitted_unit_of_work_rolls_back_all_changes(tmp_path: Path) -> None:
    database = tmp_path / "rollback.sqlite3"

    with pytest.raises(RuntimeError):
        with SqliteUnitOfWork(database) as uow:
            dispute = Dispute(
                dispute_id=DisputeId("DSP-ROLLBACK"),
                transaction_ref=UpiTransactionRef("UPIROLLBACK"),
                customer_upi="customer@example",
                reason="rollback",
            )
            audit_hash = uow.audit.append("test", "dispute.create", "DSP-ROLLBACK", {"state": "received"})
            uow.disputes.add(dispute, audit_link_hash=audit_hash)
            raise RuntimeError("force rollback")

    with sqlite3.connect(database) as connection:
        assert connection.execute("select count(*) from disputes").fetchone()[0] == 0
        assert connection.execute("select count(*) from audit_records").fetchone()[0] == 0
        assert connection.execute("select count(*) from outbox").fetchone()[0] == 0
