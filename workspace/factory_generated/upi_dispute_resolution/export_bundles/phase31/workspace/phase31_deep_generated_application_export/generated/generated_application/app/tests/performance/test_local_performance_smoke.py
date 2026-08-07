from __future__ import annotations

from pathlib import Path
from time import perf_counter

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from generated_application.app.observability.metrics import percentile


def test_local_service_timing_smoke_without_capacity_claim(tmp_path: Path) -> None:
    database = tmp_path / "timing.sqlite3"
    service = DisputeService(SqliteUnitOfWork(database))
    samples_seconds: list[float] = []

    for index in range(20):
        started = perf_counter()
        service.create_dispute(
            CreateDisputeCommand(
                transaction_ref=f"UPIT{index:08d}",
                customer_upi=f"timing{index:02d}@example",
                reason="bounded local timing smoke",
                idempotency_key=f"idem-timing-{index}",
                correlation_id=f"corr-timing-{index}",
                owner_subject="local-owner",
            )
        )
        service.list_disputes(limit=5, cursor=0)
        samples_seconds.append(perf_counter() - started)

    assert percentile(samples_seconds, 95) < 1.0


def test_local_database_pagination_growth_smoke(tmp_path: Path) -> None:
    database = tmp_path / "growth.sqlite3"
    service = DisputeService(SqliteUnitOfWork(database))
    for index in range(30):
        service.create_dispute(
            CreateDisputeCommand(
                transaction_ref=f"UPI{index:08d}",
                customer_upi=f"cu{index:02d}@example",
                reason="bounded local growth smoke",
                idempotency_key=f"idem-{index}",
                correlation_id=f"corr-{index}",
                owner_subject="local-owner",
            )
        )

    first_page = service.list_disputes(limit=10, cursor=0)
    third_page = service.list_disputes(limit=10, cursor=20)

    assert len(first_page) == 10
    assert len(third_page) == 10
    assert first_page[0].dispute_id.value != third_page[0].dispute_id.value
