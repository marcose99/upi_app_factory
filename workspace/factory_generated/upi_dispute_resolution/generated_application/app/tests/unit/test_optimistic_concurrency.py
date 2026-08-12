from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.application.services import FailedDebitRuntimeService
from generated_application.app.domain.entities import Dispute, DisputeState
from generated_application.app.domain.exceptions import OptimisticConcurrencyError, ValidationFailed
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork


def test_stale_write_is_rejected_and_version_only_increments_once(tmp_path: Path) -> None:
    database = tmp_path / "concurrency.sqlite3"
    dispute = Dispute(
        dispute_id=DisputeId("DSP-CONCURRENCY"),
        transaction_ref=UpiTransactionRef("UPICONCURRENCY"),
        customer_upi="customer@example",
        reason="concurrency",
        version=1,
    )

    with SqliteUnitOfWork(database) as uow:
        uow.disputes.add(dispute)
        uow.commit()

    with SqliteUnitOfWork(database) as first:
        loaded = first.disputes.get("DSP-CONCURRENCY")
        assert loaded is not None
        loaded.state = DisputeState.REJECTED
        first.disputes.save(loaded, expected_version=1)
        first.commit()

    with SqliteUnitOfWork(database) as second:
        stale = second.disputes.get("DSP-CONCURRENCY")
        assert stale is not None
        stale.state = DisputeState.CLOSED
        with pytest.raises(OptimisticConcurrencyError):
            second.disputes.save(stale, expected_version=1)
        second.commit()

    with SqliteUnitOfWork(database) as verifier:
        current = verifier.disputes.get("DSP-CONCURRENCY")
        assert current is not None
        assert current.version == 2
        assert current.state == DisputeState.REJECTED
        verifier.commit()


def test_failed_debit_service_requires_positive_matching_expected_version() -> None:
    case = {"version": 7}
    with pytest.raises(ValidationFailed, match="expected_version is required"):
        FailedDebitRuntimeService._expected_current_version(case, None)
    with pytest.raises(ValidationFailed, match="at least 1"):
        FailedDebitRuntimeService._expected_current_version(case, 0)
    with pytest.raises(OptimisticConcurrencyError, match="stale write"):
        FailedDebitRuntimeService._expected_current_version(case, 6)
    assert FailedDebitRuntimeService._expected_current_version(case, 7) == 7
