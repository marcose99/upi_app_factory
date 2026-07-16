from __future__ import annotations

from pathlib import Path

import pytest

from factory.operator_portal.runtime_contracts import RuntimeContractError
from factory.operator_portal.runtime_network_policy import normalize_runtime_url
from factory.operator_portal.runtime_store import RuntimeStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "base_url,endpoint",
    [
        ("http://127.0.0.1:18042", "//example.com/escape"),
        ("http://[::1]:18042", "/health"),
        ("http://localhost:18042", "/../etc/passwd"),
        ("https://127.0.0.1:18042", "/health"),
    ],
)
def test_ssrf_matrix_rejected(base_url: str, endpoint: str) -> None:
    with pytest.raises(RuntimeContractError):
        normalize_runtime_url(base_url=base_url, method="GET", endpoint=endpoint, owned_port=18042)


def test_stale_process_identity_is_detected(tmp_path: Path) -> None:
    from factory.operator_portal.runtime_contracts import ProcessIdentity, RuntimeState, RuntimeStatus
    from factory.operator_portal.runtime_store import default_binding
    from factory.operator_portal.runtime_supervisor import RuntimeSupervisor

    store = RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "runtime")
    binding = default_binding(PROJECT_ROOT, run_id="phase50_stale", port=18042)
    store.write_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            binding=binding,
            process=ProcessIdentity(pid=999999, process_start_time="never", executable="python"),
            health={"status": "ok"},
            updated_at_utc="2026-07-16T00:00:00Z",
        )
    )
    status = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store).status(run_id="phase50_stale", port=18042)
    assert status.state == RuntimeState.STALE
