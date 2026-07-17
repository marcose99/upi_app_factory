from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest
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
        env={**dict(env), **os.environ},
        text=True,
        capture_output=True,
        check=True,
    )


def test_phase13p_fresh_clone_replay_and_validator_pass(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replay_root = tmp_path / "phase13p_replay_workspace"
    monkeypatch.setenv("PHASE13P_REPLAY_ROOT", str(replay_root))

    result = run_script("run_phase13p_fresh_clone_handover_replay.py")
    output = cast(dict[str, Any], json.loads(result.stdout))
    assert output["passed"] is True
    assert output["phase"] == "Phase 13P"
    assert output["baseline_tag"] == "v0.13.14-local-runnable-operator-demo-pack"
    assert output["health_status"] == "ok"
    assert output["demo_status"] == "RESOLVED"
    assert output["verifier_passed"] is True
    operator_pack_dir = pathlib.Path(str(output["operator_pack_dir"]))
    assert operator_pack_dir.is_relative_to(replay_root)
    assert (replay_root / "repo_clone").is_dir()

    validation = run_script("validate_phase13p_fresh_clone_handover_replay.py")
    payload = cast(dict[str, Any], json.loads(validation.stdout))
    assert payload["passed"] is True
    assert payload["phase"] == "Phase 13P"
    assert payload["health_status"] == "ok"
    assert payload["demo_status"] == "RESOLVED"
    assert payload["verifier_passed"] is True
