from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tools.factory_control_plane.adapters import (
    AutonomousSupervisorAdapter,
    LifecycleOrchestratorAdapter,
    closure_attestation,
)
from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.evidence import seal_directory
from tools.factory_control_plane.worker import InboxWorker


ROOT = Path(__file__).resolve().parents[2]
SELF_TEST = ROOT / "config/control_plane/campaigns/control_plane_self_test.json"
POLICY = ROOT / "config/control_plane/standing_policy.json"


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SELF_TEST.read_text(encoding="utf-8")))


def test_inbox_worker_success_and_quarantine(tmp_path: Path) -> None:
    engine = ControlPlaneEngine(ROOT, tmp_path / "state", POLICY)
    worker = InboxWorker(tmp_path / "inbox", engine)
    try:
        shutil.copy2(SELF_TEST, tmp_path / "inbox/pending/self.json")
        assert worker.run_once()["status"] == "completed"
        assert (tmp_path / "inbox/completed/self.json.result.json").is_file()
        bad = _payload()
        bad["unexpected"] = True
        (tmp_path / "inbox/pending/bad.json").write_text(json.dumps(bad), encoding="utf-8")
        failed = worker.run_once()
        assert failed["status"] == "failed"
        assert (tmp_path / "inbox/failed/bad.json").is_file()
        assert (tmp_path / "inbox/failed/bad.json.result.json").is_file()
    finally:
        engine.close()


def test_evidence_sealing_and_symlink_rejection(tmp_path: Path) -> None:
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "result.json").write_text("{}", encoding="utf-8")
    sealed = seal_directory(source, tmp_path / "sealed")
    assert Path(sealed["archive"]).is_file()
    (source / "link").symlink_to(source / "result.json")
    with pytest.raises(ControlPlaneError, match="symlink"):
        seal_directory(source, tmp_path / "sealed2")


def test_adapter_contracts() -> None:
    lifecycle = LifecycleOrchestratorAdapter()
    supervisor = AutonomousSupervisorAdapter()
    assert lifecycle.available()
    assert supervisor.available()
    assert lifecycle.contract()["entrypoint"] == "bin/upi-app-factory-lifecycle"
    assert closure_attestation("phase46a", Path("evidence/phase46a"))[
        "regeneration"
    ] == "forbidden during later campaign execution"


def test_cli_self_test_and_rerun_behavior(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "bin/upi-app-factory-control-plane",
        "--state-root",
        str(tmp_path / "state"),
        "run",
        str(SELF_TEST),
    ]
    first = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    first_payload = json.loads(first.stdout)
    assert first_payload["status"] == "closed"
    second = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second.stdout)
    assert second_payload["status"] == "closed"
    assert second_payload["summary"]["completed_activities"] == 3


def test_policy_explain_cli(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "bin/upi-app-factory-control-plane",
        "--state-root",
        str(tmp_path / "state"),
        "policy-explain",
        "create_tag",
        "LOW",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "pause"
