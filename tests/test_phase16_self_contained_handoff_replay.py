from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
PHASE_DIR = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase16"
AUDIT = PHASE_DIR / "self_contained_handoff_replay_hardening_audit.json"
REPLAY = PHASE_DIR / "self_contained_full_fresh_clone_replay_result.json"
VALIDATOR = ROOT / "scripts" / "validate_phase16_self_contained_handoff_replay.py"
RUNNER = ROOT / "scripts" / "run_phase16_self_contained_handoff_replay.py"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return cast(dict[str, Any], data)


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_phase16_audit_preserves_governance_boundaries() -> None:
    audit = load_json(AUDIT)
    assert audit["phase"] == "16"
    assert audit["factory_does_not_self_certify"] is True
    assert audit["official_certification_claimed"] is False
    assert audit["certification_ready_not_certified_boundary_preserved"] is True
    assert audit["self_contained_full_fresh_clone_gate_enabled"] is True


def test_phase16_runner_readonly_gates_passed() -> None:
    audit = load_json(AUDIT)
    assert audit["read_only_gates_executed"] is True
    assert audit["read_only_gates_passed"] is True
    statuses = {item["gate_id"]: item["status"] for item in audit["read_only_gate_results"]}
    assert statuses["phase13g_legacy_drift_guardrail"] == "PASS"
    assert statuses["phase15_artifact_validator"] == "PASS"
    assert statuses["ruff_static_hygiene"] == "PASS"
    assert statuses["mypy_static_typing"] == "PASS"


def test_phase16_validator_accepts_committed_artifacts() -> None:
    completed = run_command([sys.executable, str(VALIDATOR)])
    assert completed.returncode == 0, completed.stderr
    assert "Phase 16 self-contained handoff replay hardening artifacts validated" in completed.stdout


def test_phase16_replay_result_when_committed_is_governed() -> None:
    if not REPLAY.exists():
        return
    replay = load_json(REPLAY)
    assert replay["status"] == "PASS"
    assert replay["full_pytest_returncode"] == 0
    assert replay["certification_claimed"] is False
    assert replay["official_certification_granted_by_factory"] is False
    assert replay["clone_local_virtualenv_required"] is False
    assert replay["hidden_local_workspace_state_required"] is False


def test_phase16_runner_is_directly_executable_with_temp_audit(tmp_path: Path) -> None:
    temp_audit = tmp_path / "phase16_audit.json"
    completed = run_command([sys.executable, str(RUNNER), "--audit-out", str(temp_audit)])
    assert completed.returncode == 0, completed.stderr
    data = load_json(temp_audit)
    assert data["phase"] == "16"
    assert data["factory_does_not_self_certify"] is True
