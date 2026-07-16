from __future__ import annotations

import socket
from pathlib import Path

import pytest

from factory.operator_portal.runtime_contracts import RuntimeContractError, RuntimeState
from factory.operator_portal.runtime_store import RuntimeStore
from factory.operator_portal.runtime_supervisor import RuntimeSupervisor


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        pytest.skip("local socket creation is blocked by the execution sandbox")


def test_start_status_duplicate_stop_and_no_orphan(tmp_path: Path) -> None:
    port = free_port()
    store = RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "runtime")
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    run_id = "phase50_supervisor"
    try:
        started = supervisor.start(run_id=run_id, port=port, readiness_timeout=10.0)
        assert started.state == RuntimeState.READY
        duplicate = supervisor.start(run_id=run_id, port=port)
        assert duplicate.process == started.process
        status = supervisor.status(run_id=run_id, port=port)
        assert status.health["status"] == "ok"
    finally:
        stopped = supervisor.stop(run_id=run_id, port=port)
    assert stopped.state == RuntimeState.STOPPED
    assert stopped.process is None
    assert stopped.health["orphan_detected"] is False


def test_port_collision_fails_closed(tmp_path: Path) -> None:
    port = free_port()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError:
        pytest.skip("local socket creation is blocked by the execution sandbox")
    with sock:
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
        supervisor = RuntimeSupervisor(
            project_root=PROJECT_ROOT,
            store=RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "runtime"),
        )
        with pytest.raises(RuntimeContractError):
            supervisor.start(run_id="phase50_collision", port=port, readiness_timeout=0.5)
