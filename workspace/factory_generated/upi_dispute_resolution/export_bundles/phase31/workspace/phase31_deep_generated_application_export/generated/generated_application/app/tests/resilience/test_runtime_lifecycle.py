from __future__ import annotations

from pathlib import Path

from generated_application.app.runtime import RuntimeLifecycle


def test_startup_liveness_readiness_drain_and_shutdown(tmp_path: Path) -> None:
    runtime = RuntimeLifecycle(tmp_path / "runtime.sqlite3")

    assert runtime.startup_status()[0] == 503
    runtime.startup()

    assert runtime.startup_status()[0] == 200
    assert runtime.liveness()[0] == 200
    assert runtime.readiness()[0] == 200

    drain = runtime.begin_drain()
    assert drain["status"] == "draining"
    assert runtime.liveness()[0] == 200
    assert runtime.readiness()[0] == 503

    runtime.shutdown()
    assert runtime.liveness()[0] == 503
    assert runtime.readiness()[0] == 503
    assert "liveness_disabled" in runtime.shutdown_checks


def test_restart_recovers_readiness_with_existing_local_database(tmp_path: Path) -> None:
    database = tmp_path / "restart.sqlite3"
    first = RuntimeLifecycle(database)
    first.startup()
    first.shutdown()

    restarted = RuntimeLifecycle(database)
    restarted.startup()

    assert restarted.startup_status()[0] == 200
    assert restarted.liveness()[0] == 200
    assert restarted.readiness()[0] == 200
    assert restarted.dependency_health()["sqlite"]["status"] == "ok"
