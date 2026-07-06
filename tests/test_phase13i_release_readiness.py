from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
    / "phase13i"
    / "release_readiness_audit.json"
)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)


def test_phase13i_audit_and_validator_pass() -> None:
    run_command([sys.executable, "scripts/run_phase13i_release_readiness_audit.py"])
    result = run_command([sys.executable, "scripts/validate_phase13i_release_readiness.py"])
    assert '"passed": true' in result.stdout


def test_phase13i_evidence_is_deterministic() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert data["evidence_determinism"]["uses_current_commit_hash"] is False
    assert data["evidence_determinism"]["uses_wall_clock_timestamp"] is False
    assert data["baseline_tag"] == "v0.13.7-release-state-lineage-registry"


def test_phase13i_operator_handover_has_no_missing_entries() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    handover_checks = [
        item for item in data["operator_smoke_checks"] if item["command"] == "./factoryctl handover"
    ]
    assert len(handover_checks) == 1
    assert handover_checks[0]["passed"] is True
    assert handover_checks[0]["handover_missing_entries"] is False
