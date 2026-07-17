from __future__ import annotations

import datetime as dt
import io
import json
import logging
from pathlib import Path

import pytest

from factory.application_engineering.local_platform_kernel import (
    AuditLog,
    AuthorizationDenied,
    CorrelationContext,
    DeterministicIdGenerator,
    FictionalLocalAuthorizer,
    FixedClock,
    IdempotencyStore,
    JsonRedactingFormatter,
    MetricsRegistry,
    OptimisticConcurrencyError,
    Principal,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteUnitOfWork,
    SQLiteVersionedRepository,
    TransactionalOutbox,
    TypedId,
)


def fixed_clock() -> FixedClock:
    return FixedClock(dt.datetime(2026, 7, 17, 10, 0, tzinfo=dt.timezone.utc))


def migrated_factory(tmp_path: Path) -> SQLiteConnectionFactory:
    factory = SQLiteConnectionFactory(tmp_path / "kernel.sqlite3")
    with factory.connect() as connection:
        SQLiteMigrator().apply(connection, fixed_clock())
    return factory


def test_rollback_removes_repository_and_outbox_changes(tmp_path: Path) -> None:
    factory = migrated_factory(tmp_path)
    item_id = TypedId("case", "CASE-1")

    with pytest.raises(RuntimeError):
        with SQLiteUnitOfWork(factory) as uow:
            SQLiteVersionedRepository(uow.connection).save(item_id, {"status": "received"})
            TransactionalOutbox(uow.connection, fixed_clock()).enqueue(
                TypedId("message", "MSG-1"), "case.created", {"case": "CASE-1"}
            )
            raise RuntimeError("force rollback")

    with factory.connect() as connection:
        assert SQLiteVersionedRepository(connection).get(item_id) is None
        assert TransactionalOutbox(connection, fixed_clock()).pending() == []


def test_migrations_are_repeatable_and_ledged_once(tmp_path: Path) -> None:
    factory = migrated_factory(tmp_path)
    with factory.connect() as connection:
        SQLiteMigrator().apply(connection, fixed_clock())
        versions = connection.execute("SELECT version FROM kernel_migrations ORDER BY version").fetchall()

    assert [row["version"] for row in versions] == [1, 2, 3, 4, 5]


def test_optimistic_concurrency_conflict_is_reported(tmp_path: Path) -> None:
    factory = migrated_factory(tmp_path)
    item_id = TypedId("case", "CASE-2")
    with factory.connect() as connection:
        repo = SQLiteVersionedRepository(connection)
        assert repo.save(item_id, {"status": "received"}, expected_version=0) == 1
        assert repo.save(item_id, {"status": "validated"}, expected_version=1) == 2
        with pytest.raises(OptimisticConcurrencyError):
            repo.save(item_id, {"status": "closed"}, expected_version=1)


def test_idempotency_replays_original_result_without_rerunning_handler(tmp_path: Path) -> None:
    factory = migrated_factory(tmp_path)
    calls = 0

    def handler() -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"result": "created"}

    with factory.connect() as connection:
        store = IdempotencyStore(connection, fixed_clock())
        first, first_replay = store.replay_or_record("idem-1", {"amount": "10.00"}, handler)
        second, second_replay = store.replay_or_record("idem-1", {"amount": "10.00"}, handler)

    assert first == second == {"result": "created"}
    assert first_replay is False
    assert second_replay is True
    assert calls == 1


def test_audit_hash_chain_detects_tampering(tmp_path: Path) -> None:
    factory = migrated_factory(tmp_path)
    with factory.connect() as connection:
        audit = AuditLog(connection, fixed_clock())
        audit.append("principal.local", "create", "case:CASE-3", {"status": "received"})
        audit.append("principal.local", "validate", "case:CASE-3", {"status": "validated"})
        assert audit.verify() is True
        connection.execute("UPDATE audit_log SET payload_json = ? WHERE sequence = 1", ('{"status":"changed"}',))
        assert audit.verify() is False


def test_outbox_is_atomic_with_unit_of_work_commit(tmp_path: Path) -> None:
    factory = migrated_factory(tmp_path)

    with SQLiteUnitOfWork(factory) as uow:
        TransactionalOutbox(uow.connection, fixed_clock()).enqueue(
            TypedId("message", "MSG-2"), "case.validated", {"case": "CASE-4"}
        )

    with factory.connect() as connection:
        pending = TransactionalOutbox(connection, fixed_clock()).pending()
    assert pending == [
        {
            "message_id": "message:MSG-2",
            "topic": "case.validated",
            "payload": {"case": "CASE-4"},
        }
    ]


def test_json_logging_redacts_sensitive_fields_and_adds_correlation() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonRedactingFormatter())
    logger = logging.getLogger("phase54-test")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    with CorrelationContext("corr-123"):
        logger.info("processed", extra={"payload": {"token": "secret-value", "safe": "visible"}})

    payload = json.loads(stream.getvalue())
    assert payload["correlation_id"] == "corr-123"
    assert payload["payload"]["token"] == "[REDACTED]"
    assert payload["payload"]["safe"] == "visible"
    assert "secret-value" not in stream.getvalue()


def test_authorization_denial_is_explicit() -> None:
    authorizer = FictionalLocalAuthorizer({"viewer": {"case.read"}})
    principal = Principal("fictional-user", frozenset({"viewer"}))

    with pytest.raises(AuthorizationDenied):
        authorizer.require(principal, "case.close", "case:CASE-5")


def test_metrics_counter_and_text_exposition_are_deterministic() -> None:
    metrics = MetricsRegistry()
    metrics.increment("requests_total", route="/ready")
    metrics.increment("requests_total", route="/ready")
    metrics.increment("authorizations_denied_total")

    assert metrics.get("requests_total", route="/ready") == 2
    assert metrics.expose_text() == (
        "authorizations_denied_total 1\n"
        'requests_total{route="/ready"} 2\n'
    )


def test_deterministic_id_port_repeats_for_same_seed() -> None:
    first = DeterministicIdGenerator("seed").new_id("message")
    second = DeterministicIdGenerator("seed").new_id("message")

    assert first == second
    assert str(first).startswith("message:")
