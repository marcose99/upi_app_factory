from __future__ import annotations

import json
import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_phase13v_policy_governed_self_repairing_generation(tmp_path: pathlib.Path) -> None:
    generation_output = tmp_path / "generation.json"
    validation_output = tmp_path / "validation.json"

    generation = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase13v_policy_governed_self_repairing_generation.py",
            "--output",
            str(generation_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generation.returncode == 0, generation.stdout + generation.stderr
    generation_payload = json.loads(generation_output.read_text(encoding="utf-8"))
    assert generation_payload["passed"] is True
    assert generation_payload["repair_attempts"] == 1
    assert generation_payload["policy_decision_count"] == 1
    assert generation_payload["openai_api_key_required"] is False

    validation = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase13v_policy_governed_self_repairing_generation.py",
            "--output",
            str(validation_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
    validation_payload = json.loads(validation_output.read_text(encoding="utf-8"))
    assert validation_payload["passed"] is True
    assert validation_payload["policy_id"] == "POL-13V-POLICY-GOVERNED-GENERATION"
    assert validation_payload["llm_runtime_mode"] == "deterministic_local"
    assert validation_payload["openai_api_key_required"] is False
