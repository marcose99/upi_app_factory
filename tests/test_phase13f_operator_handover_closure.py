from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"


def run_python_script(relative_path: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [os.environ.get("PYTHON", "python3"), relative_path],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_phase13f_operator_handover_audit_passes() -> None:
    result = run_python_script("scripts/run_phase13f_operator_handover_audit.py")
    assert result.returncode == 0, result.stdout
    audit_path = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13f" / "operator_handover_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["passed"] is True
    assert audit["missing_output_lines"] == []
    assert audit["missing_documents"] == []


def test_phase13f_validator_passes() -> None:
    run_python_script("scripts/generate_phase13f_operator_handover_portal.py")
    result = run_python_script("scripts/validate_phase13f_operator_handover_closure.py")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["errors"] == []


def test_factoryctl_handover_has_no_missing_entries() -> None:
    result = subprocess.run(
        [str(PROJECT_ROOT / "factoryctl"), "handover"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "[MISSING]" not in result.stdout
    assert "docs/phase13c/agent_runtime_handover.md" in result.stdout
