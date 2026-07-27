#!/usr/bin/env python3
from __future__ import annotations

import atexit
import compileall
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

_STARTUP_PYCACHE = tempfile.TemporaryDirectory(
    prefix="phase71_82_wave_b_startup_pycache_"
)
sys.pycache_prefix = _STARTUP_PYCACHE.name
atexit.register(_STARTUP_PYCACHE.cleanup)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.generators.mock_dispute_app_generator import generate  # noqa: E402


RUN_ID = "phase71_82_wave_b_data_integrity_eventing_repair1"
TEMPLATE_GENERATED_ROOT = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
)
REQUIRED_WAVE_B_FILES = {
    "generated_application/app/infrastructure/persistence/migrations.py",
    "generated_application/app/infrastructure/persistence/audit_log.py",
    "generated_application/app/infrastructure/persistence/outbox.py",
    "generated_application/app/infrastructure/persistence/inbox.py",
    "generated_application/asyncapi.yaml",
    "generated_application/app/tests/integration/test_transactional_integrity.py",
    "generated_application/app/tests/unit/test_optimistic_concurrency.py",
    "generated_application/app/tests/replay/test_outbox_replay_and_inbox.py",
    "generated_application/app/tests/resilience/test_migrations_restart.py",
    "generated_application/app/tests/contract/test_event_contract.py",
}


def bytecode_artifacts(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    artifacts: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}:
            relative_path = path.relative_to(root).as_posix()
            if path.is_file():
                artifacts[relative_path] = (
                    f"file:{path.stat().st_size}:"
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
                )
            else:
                artifacts[relative_path] = "dir"
    return artifacts


def compile_without_source_cache(paths: list[Path]) -> None:
    previous_prefix = sys.pycache_prefix
    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_b_pycache_") as cache_dir:
        sys.pycache_prefix = cache_dir
        try:
            for path in paths:
                if not compileall.compile_dir(
                    str(path),
                    quiet=1,
                    force=True,
                    legacy=False,
                ):
                    raise RuntimeError(f"Bytecode compilation failed for {path}")
        finally:
            sys.pycache_prefix = previous_prefix


def run_functional_smoke(generated_root: Path) -> list[str]:
    previous_prefix = sys.pycache_prefix
    previous_path = list(sys.path)
    checks: list[str] = []

    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_b_import_cache_") as cache_dir:
        sys.pycache_prefix = cache_dir
        sys.path.insert(0, str(generated_root))
        try:
            from generated_application.app.application.commands import CreateDisputeCommand
            from generated_application.app.application.services import DisputeService
            from generated_application.app.domain.entities import Dispute, DisputeState
            from generated_application.app.domain.exceptions import (
                MigrationDriftError,
                OptimisticConcurrencyError,
            )
            from generated_application.app.domain.value_objects import (
                DisputeId,
                UpiTransactionRef,
            )
            from generated_application.app.infrastructure.persistence.migrations import (
                apply_migrations,
            )
            from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import (
                SqliteUnitOfWork,
            )

            with tempfile.TemporaryDirectory(prefix="phase71_82_wave_b_db_") as db_dir:
                db_root = Path(db_dir)

                database = db_root / "atomic.sqlite3"
                dispute_id = DisputeService(SqliteUnitOfWork(database)).create_dispute(
                    CreateDisputeCommand(
                        transaction_ref="UPI12345",
                        customer_upi="customer@example",
                        reason="failed debit",
                        idempotency_key="idem-1",
                        correlation_id="corr-1",
                    )
                )
                with sqlite3.connect(database) as connection:
                    dispute = connection.execute(
                        "select version, audit_link_hash from disputes where dispute_id = ?",
                        (dispute_id,),
                    ).fetchone()
                    audit = connection.execute(
                        "select record_hash from audit_records"
                    ).fetchone()
                    outbox = connection.execute(
                        "select envelope_json from outbox"
                    ).fetchone()
                assert dispute is not None
                assert audit is not None
                assert outbox is not None
                assert dispute[0] == 1
                assert dispute[1] == audit[0]
                assert audit[0] in outbox[0]
                checks.append("aggregate_audit_outbox_atomicity")

                rollback_db = db_root / "rollback.sqlite3"
                try:
                    with SqliteUnitOfWork(rollback_db) as uow:
                        dispute = Dispute(
                            dispute_id=DisputeId("DSP-ROLLBACK"),
                            transaction_ref=UpiTransactionRef("UPIROLLBACK"),
                            customer_upi="customer@example",
                            reason="rollback",
                        )
                        audit_hash = uow.audit.append(
                            "test",
                            "dispute.create",
                            "DSP-ROLLBACK",
                            {"state": "received"},
                        )
                        uow.disputes.add(dispute, audit_link_hash=audit_hash)
                        raise RuntimeError("force rollback")
                except RuntimeError:
                    pass
                with sqlite3.connect(rollback_db) as connection:
                    assert connection.execute(
                        "select count(*) from disputes"
                    ).fetchone()[0] == 0
                    assert connection.execute(
                        "select count(*) from audit_records"
                    ).fetchone()[0] == 0
                    assert connection.execute(
                        "select count(*) from outbox"
                    ).fetchone()[0] == 0
                checks.append("transaction_rollback")

                concurrency_db = db_root / "concurrency.sqlite3"
                dispute = Dispute(
                    dispute_id=DisputeId("DSP-CONCURRENCY"),
                    transaction_ref=UpiTransactionRef("UPICONCURRENCY"),
                    customer_upi="customer@example",
                    reason="concurrency",
                    version=1,
                )
                with SqliteUnitOfWork(concurrency_db) as uow:
                    uow.disputes.add(dispute)
                    uow.commit()
                with SqliteUnitOfWork(concurrency_db) as first:
                    loaded = first.disputes.get("DSP-CONCURRENCY")
                    assert loaded is not None
                    loaded.state = DisputeState.REJECTED
                    first.disputes.save(loaded, expected_version=1)
                    first.commit()
                with SqliteUnitOfWork(concurrency_db) as second:
                    stale = second.disputes.get("DSP-CONCURRENCY")
                    assert stale is not None
                    stale.state = DisputeState.CLOSED
                    try:
                        second.disputes.save(stale, expected_version=1)
                    except OptimisticConcurrencyError:
                        pass
                    else:
                        raise AssertionError("stale write was accepted")
                    second.commit()
                checks.append("optimistic_concurrency")

                replay_db = db_root / "replay.sqlite3"
                DisputeService(SqliteUnitOfWork(replay_db)).create_dispute(
                    CreateDisputeCommand(
                        transaction_ref="UPIREPLAY",
                        customer_upi="customer@example",
                        reason="restart replay",
                        idempotency_key="idem-replay",
                        correlation_id="corr-replay",
                    )
                )
                with SqliteUnitOfWork(replay_db) as restarted:
                    pending = restarted.outbox.pending()
                    assert len(pending) == 1
                    assert pending[0]["envelope"]["schema_version"] == (
                        "upi_app_factory.event_envelope.v1"
                    )
                    restarted.outbox.mark_dispatched(str(pending[0]["message_id"]))
                    restarted.commit()
                with SqliteUnitOfWork(replay_db) as verifier:
                    assert verifier.outbox.pending() == []
                    verifier.commit()
                checks.append("outbox_replay")

                inbox_db = db_root / "inbox.sqlite3"
                calls: list[str] = []
                with SqliteUnitOfWork(inbox_db) as uow:
                    assert uow.inbox.process_once(
                        "message-1", lambda: calls.append("handled")
                    ) is True
                    assert uow.inbox.process_once(
                        "message-1", lambda: calls.append("duplicate")
                    ) is False
                    uow.commit()
                assert calls == ["handled"]
                checks.append("inbox_duplicate_guard")

                retry_db = db_root / "inbox_retry.sqlite3"
                try:
                    with SqliteUnitOfWork(retry_db) as uow:
                        uow.inbox.process_once(
                            "message-retry",
                            lambda: (_ for _ in ()).throw(
                                RuntimeError("handler failed")
                            ),
                        )
                        uow.commit()
                except RuntimeError:
                    pass
                retry_calls: list[str] = []
                with SqliteUnitOfWork(retry_db) as uow:
                    assert uow.inbox.process_once(
                        "message-retry", lambda: retry_calls.append("handled")
                    ) is True
                    uow.commit()
                assert retry_calls == ["handled"]
                checks.append("inbox_failed_consumer_retry")

                drift_db = db_root / "drift.sqlite3"
                with sqlite3.connect(drift_db) as connection:
                    apply_migrations(connection)
                    connection.execute(
                        "update schema_migrations set checksum = ? where version = 2",
                        ("tampered",),
                    )
                    connection.commit()
                with sqlite3.connect(drift_db) as connection:
                    try:
                        apply_migrations(connection)
                    except MigrationDriftError:
                        pass
                    else:
                        raise AssertionError("migration checksum drift was accepted")
                checks.append("migration_checksum_drift")

            asyncapi_text = (
                generated_root / "generated_application/asyncapi.yaml"
            ).read_text(encoding="utf-8")
            assert "dispute.state_changed" in asyncapi_text
            assert "upi_app_factory.event_envelope.v1" in asyncapi_text
            checks.append("asyncapi_event_contract")
        finally:
            sys.path = previous_path
            sys.pycache_prefix = previous_prefix

    return checks


def validate() -> dict[str, Any]:
    before_template_bytecode = bytecode_artifacts(TEMPLATE_GENERATED_ROOT)

    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_b_generation_") as workspace:
        result = generate(run_id=RUN_ID, workspace_root=Path(workspace), clean=True)
        generated_root = result.output_dir / "generated"
        emitted_files = {item.relative_path for item in result.generated_files}
        missing = sorted(REQUIRED_WAVE_B_FILES - emitted_files)
        if missing:
            raise RuntimeError(f"Fresh generated output missing Wave B files: {missing}")

        generated_before_bytecode = bytecode_artifacts(generated_root)
        compile_without_source_cache([generated_root])
        generated_after_bytecode = bytecode_artifacts(generated_root)
        if generated_after_bytecode != generated_before_bytecode:
            raise RuntimeError("Validation wrote bytecode inside fresh generated output")

        functional_checks = run_functional_smoke(generated_root)
        generated_after_bytecode = bytecode_artifacts(generated_root)
        if generated_after_bytecode != generated_before_bytecode:
            raise RuntimeError("Validation wrote bytecode inside fresh generated output")

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        proof: dict[str, Any] = {
            "passed": True,
            "run_id": result.run_id,
            "generation_mode": manifest["generation_mode"],
            "generated_file_count": len(result.generated_files),
            "compiled_roots": [
                "fresh temporary generated output",
            ],
            "bytecode_cache_policy": "sys.pycache_prefix redirected to temporary directory",
            "functional_smoke_checks": functional_checks,
            "generated_pytest_files_preserved": sorted(
                relative_path
                for relative_path in emitted_files
                if "/app/tests/" in relative_path and relative_path.endswith(".py")
            ),
        }

    after_template_bytecode = bytecode_artifacts(TEMPLATE_GENERATED_ROOT)
    if after_template_bytecode != before_template_bytecode:
        changed = sorted(
            set(before_template_bytecode) ^ set(after_template_bytecode)
            | {
                path
                for path in set(before_template_bytecode) & set(after_template_bytecode)
                if before_template_bytecode[path] != after_template_bytecode[path]
            }
        )
        raise RuntimeError(f"Validation mutated template bytecode artifacts: {changed}")

    return proof


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2) + "\n")
    except Exception as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
