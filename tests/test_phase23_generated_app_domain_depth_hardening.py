from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase23_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase23_generated_app_domain_depth_hardening.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase23_runner_emits_temp_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    workflow = tmp_path / "workflow.json"
    scenario = tmp_path / "scenario.json"
    gaps = tmp_path / "gaps.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase23_generated_app_domain_depth_hardening.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--workflow-out",
            str(workflow),
            "--scenario-out",
            str(scenario),
            "--gap-out",
            str(gaps),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = load_json(audit)
    assert payload["status"] == "GENERATED_APP_DOMAIN_DEPTH_HARDENING_READY"
    assert payload["official_certification_claimed"] is False
