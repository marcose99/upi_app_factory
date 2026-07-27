from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork


def test_outbox_survives_restart_until_replayed(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    DisputeService(SqliteUnitOfWork(database)).create_dispute(
        CreateDisputeCommand(
            transaction_ref="UPIREPLAY",
            customer_upi="customer@example",
            reason="restart replay",
            idempotency_key="idem-replay",
            correlation_id="corr-replay",
        )
    )

    with SqliteUnitOfWork(database) as restarted:
        pending = restarted.outbox.pending()
        assert len(pending) == 1
        assert pending[0]["envelope"]["schema_version"] == "upi_app_factory.event_envelope.v1"
        restarted.outbox.mark_dispatched(str(pending[0]["message_id"]))
        restarted.commit()

    with SqliteUnitOfWork(database) as verifier:
        assert verifier.outbox.pending() == []
        verifier.commit()


def test_inbox_rejects_duplicate_delivery(tmp_path: Path) -> None:
    database = tmp_path / "inbox.sqlite3"
    calls: list[str] = []

    with SqliteUnitOfWork(database) as uow:
        assert uow.inbox.process_once("message-1", lambda: calls.append("handled")) is True
        assert uow.inbox.process_once("message-1", lambda: calls.append("duplicate")) is False
        uow.commit()

    assert calls == ["handled"]


def test_inbox_allows_retry_after_handler_failure(tmp_path: Path) -> None:
    database = tmp_path / "inbox_failure.sqlite3"
    calls: list[str] = []

    try:
        with SqliteUnitOfWork(database) as uow:
            uow.inbox.process_once(
                "message-retry",
                lambda: (_ for _ in ()).throw(RuntimeError("handler failed")),
            )
            uow.commit()
    except RuntimeError:
        pass

    with SqliteUnitOfWork(database) as uow:
        assert uow.inbox.process_once("message-retry", lambda: calls.append("handled")) is True
        uow.commit()

    assert calls == ["handled"]
