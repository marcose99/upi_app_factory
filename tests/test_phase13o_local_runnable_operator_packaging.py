from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import Any, cast

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    path_parts = [
        str(PROJECT_ROOT / "src"),
        str(PROJECT_ROOT / "scripts"),
        str(PROJECT_ROOT),
        env.get("PYTHONPATH", ""),
    ]
    env["PYTHONPATH"] = ":".join(part for part in path_parts if part)
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / script_name), *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_phase13o_packager_and_validator_pass() -> None:
    result = run_script("run_phase13o_local_runnable_operator_packaging.py")
    output = cast(dict[str, Any], json.loads(result.stdout))
    assert output["passed"] is True
    assert output["phase"] == "Phase 13O"
    assert output["orchestration_framework"] in {"langgraph", "stdlib_state_graph"}
    assert output["graph_type"] == "StateGraph"
    assert output["one_command_demo"] == "./run_operator_demo.sh"
    runtime_path = (
        PROJECT_ROOT
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
        / "operator_handoff"
        / "phase13o_local_runnable_pack"
        / "operator_runtime.py"
    )
    runtime_text = runtime_path.read_text(encoding="utf-8")
    assert "from phase13m_dispute_lifecycle_app.api import" not in runtime_text
    assert 'import_module("phase13m_dispute_lifecycle_app.api")' in runtime_text

    validation = run_script("validate_phase13o_local_runnable_operator_packaging.py")
    payload = cast(dict[str, Any], json.loads(validation.stdout))
    assert payload["passed"] is True
    assert payload["health_status"] == "ok"
    assert payload["demo_status"] == "RESOLVED"
    assert payload["verifier_passed"] is True
