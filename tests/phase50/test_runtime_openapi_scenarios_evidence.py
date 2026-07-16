from __future__ import annotations

import socket
from pathlib import Path
import zipfile

import pytest

from factory.operator_portal.runtime_evidence import RuntimeEvidenceService
from factory.operator_portal.runtime_openapi import RuntimeOpenAPIService
from factory.operator_portal.runtime_scenarios import ScenarioRunner
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


def test_openapi_scenarios_and_evidence_bundle(tmp_path: Path) -> None:
    port = free_port()
    run_id = "phase50_e2e"
    store = RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "runtime")
    supervisor = RuntimeSupervisor(project_root=PROJECT_ROOT, store=store)
    try:
        status = supervisor.start(run_id=run_id, port=port, readiness_timeout=10.0)
        openapi = RuntimeOpenAPIService().fetch(
            base_url=f"http://127.0.0.1:{port}",
            owned_port=port,
            manifest_sha256=status.binding.manifest_sha256,
        )
        assert openapi["status"] == "available"
        assert any(item["path"] == "/disputes" and item["method"] == "POST" for item in openapi["endpoint_inventory"])

        scenarios = ScenarioRunner(store=store).run_all(
            run_id=run_id,
            base_url=f"http://127.0.0.1:{port}",
            owned_port=port,
        )
        assert scenarios["passed"] is True
    finally:
        supervisor.stop(run_id=run_id, port=port)

    evidence = RuntimeEvidenceService(project_root=PROJECT_ROOT, store=store)
    manifest = evidence.build_manifest(run_id=run_id)
    assert manifest["decision"] == "GO"
    assert manifest["validation_gates"]["approval_plaintext_absent"] is True
    archive = evidence.archive(run_id=run_id)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert all(not name.endswith("/") for name in names)
        assert all(".." not in Path(name).parts for name in names)
        assert any(name.endswith("runtime_evidence_manifest.json") for name in names)
