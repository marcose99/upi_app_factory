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


def test_phase13m_langgraph_generator_and_validator_pass() -> None:
    run_script("run_phase13m_langgraph_agentic_lifecycle_generation.py", "--quiet")
    result = run_script("validate_phase13m_langgraph_agentic_lifecycle_generation.py")
    payload = cast(dict[str, Any], json.loads(result.stdout))

    assert payload["passed"] is True
    assert payload["phase"] == "Phase 13M"
    assert payload["orchestration_framework"] in {"langgraph", "stdlib_state_graph"}
    assert payload["graph_type"] == "StateGraph"
    assert payload["generated_package"] == "phase13m_dispute_lifecycle_app"
    assert (
        "passed" in payload["pytest_output"]
        or "direct generated lifecycle checks passed" in payload["pytest_output"]
    )
