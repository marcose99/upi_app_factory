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


def test_phase13n_supervisor_repairs_and_validates() -> None:
    result = run_script("run_phase13n_langgraph_factory_self_repair_supervisor.py")
    output = cast(dict[str, Any], json.loads(result.stdout))
    assert output["passed"] is True
    assert output["phase"] == "Phase 13N"
    assert output["orchestration_framework"] == "langgraph"
    assert output["graph_type"] == "StateGraph"
    assert output["repair_applied"] is True
    assert output["attempts_used"] == 1

    validation = run_script("validate_phase13n_langgraph_factory_self_repair_supervisor.py")
    payload = cast(dict[str, Any], json.loads(validation.stdout))
    assert payload["passed"] is True
    assert payload["repair_applied"] is True
    assert payload["final_validation_passed"] is True
