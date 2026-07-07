from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase26_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase26_v1_release_candidate_consolidation.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase26_runner_emits_temp_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    gaps = tmp_path / "gaps.json"
    decision = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase26_v1_release_candidate_consolidation.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--evidence-out",
            str(evidence),
            "--gap-out",
            str(gaps),
            "--decision-out",
            str(decision),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = load_json(audit)
    assert payload["status"] == "V1_RELEASE_CANDIDATE_CONSOLIDATED"
    assert payload["official_certification_granted"] is False
