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


def test_governed_agentic_phase_runner_stops_at_human_release_gate() -> None:
    result = run_script(
        "run_governed_agentic_phase.py",
        "--objective",
        "Phase 13R governed runner smoke proof",
        "--phase-id",
        "phase13r_test_smoke",
        "--dry-run",
    )
    payload = cast(dict[str, Any], json.loads(result.stdout))
    assert payload["passed"] is True
    assert payload["phase"] == "Phase 13R"
    assert payload["orchestration_framework"] == "langgraph"
    assert payload["graph_type"] == "StateGraph"
    assert payload["status"] == "awaiting_human_release_approval"
    assert payload["human_approval_required"] is True
    assert payload["release_ready"] is True
    assert "git push" in payload["blocked_actions"]
    assert "git tag" in payload["blocked_actions"]

    validation = run_script("validate_phase13r_governed_agentic_phase_runner.py")
    validation_payload = cast(dict[str, Any], json.loads(validation.stdout))
    assert validation_payload["passed"] is True
    assert validation_payload["phase"] == "Phase 13R"
    assert validation_payload["human_approval_required"] is True
