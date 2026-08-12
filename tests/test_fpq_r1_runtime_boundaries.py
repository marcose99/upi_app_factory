from __future__ import annotations

from collections.abc import Callable
import os
import signal
from pathlib import Path
import subprocess
import sys
from typing import Any

from fastapi import HTTPException
import pytest

from factory.operator_portal.runtime_api import RuntimeAPI
from factory.operator_portal.runtime_contracts import (
    ProcessIdentity,
    RuntimeContractError,
    RuntimeState,
    RuntimeStatus,
    utc_now,
)
from factory.operator_portal.runtime_store import RuntimeStore, default_binding
from factory.operator_portal.runtime_supervisor import RuntimeSupervisor


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _current_process(supervisor: RuntimeSupervisor) -> ProcessIdentity:
    return ProcessIdentity(
        pid=os.getpid(),
        process_start_time=supervisor._process_start_time(os.getpid()),
        executable=sys.executable,
    )


def test_active_runtime_requires_process_and_exact_application_identity(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    missing_store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "missing",
    )
    port = 19041
    run_id = "fpq_runtime_missing"
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    missing_store.write_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            binding=binding,
            process=None,
            health={"status": "ok"},
            updated_at_utc=utc_now(),
        )
    )
    observed = RuntimeSupervisor(
        project_root=PROJECT_ROOT,
        store=missing_store,
    ).status(run_id=run_id, port=port)
    assert observed.state == RuntimeState.STALE

    correct_store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "correct",
    )
    run_id = "fpq_runtime_correct"
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=correct_store)
    identity = supervisor._runtime_identity_payload(run_id)
    assert set(identity) == {"app_slug", "application_version", "manifest_sha256"}
    port = 19042
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    correct_store.write_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            binding=binding,
            process=_current_process(supervisor),
            health={"status": "ok", **identity},
            updated_at_utc=utc_now(),
        )
    )
    monkeypatch.setattr(supervisor, "_health", lambda binding: {"status": "ok", **identity})
    observed = supervisor.status(run_id=run_id, port=port)
    assert observed.state == RuntimeState.READY
    assert all(observed.health[key] == value for key, value in identity.items())

    wrong_store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "wrong",
    )
    run_id = "fpq_runtime_wrong"
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=wrong_store)
    identity = supervisor._runtime_identity_payload(run_id)
    port = 19043
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    wrong_store.write_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            binding=binding,
            process=_current_process(supervisor),
            health={"status": "ok"},
            updated_at_utc=utc_now(),
        )
    )
    monkeypatch.setattr(
        supervisor,
        "_health",
        lambda binding: {"status": "ok", **identity, "application_version": "wrong"},
    )
    observed = supervisor.status(run_id=run_id, port=port)
    assert observed.state == RuntimeState.STALE


def test_compatibility_child_environment_is_bounded_and_mock_safe(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "environment")
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    captured: dict[str, Any] = {}

    class FakePopen:
        returncode = 17

        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            captured["env"] = dict(kwargs["env"])
            self.pid = os.getpid()

        def poll(self) -> int:
            return self.returncode

    canaries = {
        "UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL": "1",
        "OPENAI_API_KEY": "secret",
        "GITHUB_TOKEN": "secret",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "HTTP_PROXY": "http://proxy.invalid",
        "CUSTOM_UNRELATED_CANARY": "secret",
    }
    for key, value in canaries.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(supervisor, "_port_in_use", lambda port: False)
    supervisor.start(run_id="fpq_runtime_environment", port=19142, readiness_timeout=0.2)

    child_env = captured["env"]
    assert 0 < len(child_env) <= 20
    assert not (set(canaries) - {"UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL"}) & set(child_env)
    assert child_env["UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL"] == "0"
    assert child_env["UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE"] == "mock"
    assert child_env["UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS"] == "false"
    assert child_env["UPI_DISPUTE_ALLOW_REAL_SECRETS"] == "false"
    assert child_env["PYTHONPATH"]
    assert child_env["UPI_APP_FACTORY_RUNTIME_MANIFEST_SHA256"]


def test_wrong_identity_blocks_openapi_scenarios_and_evidence_attribution(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    state_root = tmp_path / "attribution"
    api = RuntimeAPI(project_root=PROJECT_ROOT, state_root=state_root)
    run_id = "fpq_runtime_attribution"
    port = 19044
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    identity = api.supervisor._runtime_identity_payload(run_id)
    api.store.write_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            binding=binding,
            process=_current_process(api.supervisor),
            health={"status": "ok"},
            updated_at_utc=utc_now(),
        )
    )
    monkeypatch.setattr(
        RuntimeSupervisor,
        "_health",
        lambda self, binding: {
            "status": "ok",
            **identity,
            "manifest_sha256": "0" * 64,
        },
    )
    operations: tuple[Callable[[], object], ...] = (
        lambda: api.openapi_document(run_id, port=port),
        lambda: api.run_scenarios(run_id, port=port),
        lambda: api.evidence_manifest(run_id, port=port),
    )
    for operation in operations:
        with pytest.raises(HTTPException) as exc:
            operation()
        assert exc.value.status_code == 409

def test_verified_owned_stale_runtime_is_terminated_before_stop_clears_process(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "stale_owned_stop",
    )
    run_id = "fpq_runtime_stale_owned_stop"
    port = 19045
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    process = _current_process(supervisor)
    store.write_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            binding=binding,
            process=process,
            health={"status": "ok"},
            updated_at_utc=utc_now(),
        )
    )

    monkeypatch.setattr(
        supervisor,
        "_process_matches",
        lambda candidate: candidate == process,
    )
    monkeypatch.setattr(
        supervisor,
        "_verified_health",
        lambda binding: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        supervisor,
        "_open_owned_pidfd",
        lambda candidate: 901 if candidate == process else None,
    )
    monkeypatch.setattr(
        supervisor,
        "_wait_pidfd_exit",
        lambda pidfd, *, timeout: True,
    )
    signals: list[tuple[int, signal.Signals]] = []
    closed: list[int] = []
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.signal.pidfd_send_signal",
        lambda pidfd, requested, siginfo=None, flags=0: signals.append(
            (pidfd, requested)
        ),
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.close",
        lambda pidfd: closed.append(pidfd),
    )

    stopped = supervisor.stop(run_id=run_id, port=port, timeout=0.1)

    assert stopped.state == RuntimeState.STOPPED
    assert stopped.process is None
    assert stopped.health == {"status": "stopped", "orphan_detected": False}
    assert signals == [(901, signal.SIGTERM)]
    assert closed == [901]


def test_stale_unowned_process_identity_is_never_signaled(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "stale_unowned_stop",
    )
    run_id = "fpq_runtime_stale_unowned_stop"
    port = 19046
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    process = _current_process(supervisor)
    store.write_status(
        RuntimeStatus(
            state=RuntimeState.STALE,
            binding=binding,
            process=process,
            health={"status": "stale_process_identity"},
            updated_at_utc=utc_now(),
        )
    )
    monkeypatch.setattr(supervisor, "_process_matches", lambda candidate: False)
    signals: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.killpg",
        lambda pid, requested: signals.append((pid, requested)),
    )

    stopped = supervisor.stop(run_id=run_id, port=port, timeout=0.1)

    assert stopped.state == RuntimeState.STOPPED
    assert stopped.process is None
    assert signals == []


def test_start_rejects_owned_stale_process_instead_of_returning_stale(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "stale_start",
    )
    run_id = "fpq_runtime_stale_start"
    port = 19047
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    binding = default_binding(PROJECT_ROOT, run_id=run_id, port=port)
    process = _current_process(supervisor)
    store.write_status(
        RuntimeStatus(
            state=RuntimeState.STALE,
            binding=binding,
            process=process,
            health={"status": "runtime_identity_mismatch"},
            updated_at_utc=utc_now(),
        )
    )
    monkeypatch.setattr(supervisor, "_process_matches", lambda candidate: True)
    monkeypatch.setattr(supervisor, "_port_in_use", lambda requested_port: True)

    with pytest.raises(RuntimeContractError, match="use restart or stop"):
        supervisor.start(run_id=run_id, port=port, readiness_timeout=0.1)


def test_pidfd_is_acquired_before_identity_recheck_and_signal(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "pidfd_order",
    )
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    process = _current_process(supervisor)
    events: list[tuple[object, ...]] = []

    def fake_pidfd_open(pid: int, flags: int = 0) -> int:
        events.append(("pidfd_open", pid, flags))
        return 902

    def fake_process_matches(candidate: ProcessIdentity) -> bool:
        events.append(("identity_recheck", candidate.pid))
        return True

    def fake_wait_pidfd_exit(pidfd: int, *, timeout: float) -> bool:
        events.append(("pidfd_wait", pidfd, timeout))
        return True

    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.pidfd_open",
        fake_pidfd_open,
    )
    monkeypatch.setattr(
        supervisor,
        "_process_matches",
        fake_process_matches,
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.signal.pidfd_send_signal",
        lambda pidfd, requested, siginfo=None, flags=0: events.append(
            ("pidfd_signal", pidfd, requested)
        ),
    )
    monkeypatch.setattr(
        supervisor,
        "_wait_pidfd_exit",
        fake_wait_pidfd_exit,
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.close",
        lambda pidfd: events.append(("close", pidfd)),
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.killpg",
        lambda pid, requested: pytest.fail(
            "numeric PID/process-group signalling must not be used"
        ),
    )

    supervisor._terminate_owned_process(process, timeout=0.1)

    assert events == [
        ("pidfd_open", process.pid, 0),
        ("identity_recheck", process.pid),
        ("pidfd_signal", 902, signal.SIGTERM),
        ("pidfd_wait", 902, 0.1),
        ("close", 902),
    ]


def test_pidfd_identity_mismatch_after_open_closes_without_signal(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "pidfd_identity_change",
    )
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    process = _current_process(supervisor)
    events: list[tuple[object, ...]] = []

    def fake_pidfd_open(pid: int, flags: int = 0) -> int:
        events.append(("pidfd_open", pid, flags))
        return 903

    def fake_process_matches(candidate: ProcessIdentity) -> bool:
        events.append(("identity_recheck", candidate.pid))
        return False

    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.pidfd_open",
        fake_pidfd_open,
    )
    monkeypatch.setattr(
        supervisor,
        "_process_matches",
        fake_process_matches,
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.signal.pidfd_send_signal",
        lambda pidfd, requested, siginfo=None, flags=0: pytest.fail(
            "identity-mismatched pidfd must never be signalled"
        ),
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.close",
        lambda pidfd: events.append(("close", pidfd)),
    )

    supervisor._terminate_owned_process(process, timeout=0.1)

    assert events == [
        ("pidfd_open", process.pid, 0),
        ("identity_recheck", process.pid),
        ("close", 903),
    ]


def test_pidfd_unavailable_fails_closed_without_numeric_signal(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    store = RuntimeStore(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "pidfd_unavailable",
    )
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    process = _current_process(supervisor)

    monkeypatch.delattr(
        "factory.operator_portal.runtime_supervisor.os.pidfd_open",
        raising=False,
    )
    monkeypatch.setattr(
        "factory.operator_portal.runtime_supervisor.os.killpg",
        lambda pid, requested: pytest.fail(
            "numeric PID/process-group signalling must not be used"
        ),
    )

    with pytest.raises(
        RuntimeContractError,
        match="pidfd process signalling is unavailable",
    ):
        supervisor._terminate_owned_process(process, timeout=0.1)
