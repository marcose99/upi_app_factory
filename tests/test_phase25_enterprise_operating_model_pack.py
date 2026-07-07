from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase25_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase25_enterprise_operating_model_pack.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase25_runner_emits_temp_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    raci = tmp_path / "raci.json"
    runbook = tmp_path / "runbook.json"
    governance = tmp_path / "governance.json"
    handoff = tmp_path / "handoff.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase25_enterprise_operating_model_pack.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--raci-out",
            str(raci),
            "--runbook-out",
            str(runbook),
            "--governance-out",
            str(governance),
            "--handoff-out",
            str(handoff),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = load_json(audit)
    assert payload["status"] == "ENTERPRISE_OPERATING_MODEL_PACK_READY"
    assert payload["auto_production_deployment"] is False
