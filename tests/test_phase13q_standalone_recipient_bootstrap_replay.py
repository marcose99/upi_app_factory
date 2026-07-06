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


def test_phase13q_standalone_bootstrap_replay_and_validator_pass() -> None:
    result = run_script("run_phase13q_standalone_recipient_bootstrap_replay.py")
    output = cast(dict[str, Any], json.loads(result.stdout))
    assert output["passed"] is True
    assert output["phase"] == "Phase 13Q"
    assert output["baseline_tag"] == "v0.13.15-fresh-clone-handover-replay"
    assert output["replay_mode"] == "fresh_clone_new_recipient_venv"
    assert output["health_status"] == "ok"
    assert output["demo_status"] == "RESOLVED"
    assert output["verifier_passed"] is True

    validation = run_script(
        "validate_phase13q_standalone_recipient_bootstrap_replay.py"
    )
    payload = cast(dict[str, Any], json.loads(validation.stdout))
    assert payload["passed"] is True
    assert payload["phase"] == "Phase 13Q"
    assert payload["health_status"] == "ok"
    assert payload["demo_status"] == "RESOLVED"
    assert payload["verifier_passed"] is True
