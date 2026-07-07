from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def test_phase20_runner_generates_safe_promotion_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    matrix = tmp_path / "matrix.json"
    rollback = tmp_path / "rollback.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase20_environment_promotion_governance.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--matrix-out",
            str(matrix),
            "--rollback-out",
            str(rollback),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit_data = load_json(audit)
    matrix_data = load_json(matrix)
    assert audit_data["official_certification_claimed"] is False
    assert audit_data["automatic_production_promotion_performed"] is False
    assert matrix_data["automatic_production_promotion_allowed"] is False


def test_phase20_validator_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase20_environment_promotion_governance.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
