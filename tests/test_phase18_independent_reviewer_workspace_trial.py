from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_phase18_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase18_independent_reviewer_workspace_trial.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase18_tmp_reviewer_pack_is_non_certifying(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    pack = tmp_path / "pack.json"
    checklist = tmp_path / "checklist.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase18_independent_reviewer_workspace_trial.py",
            "--audit-out",
            str(audit),
            "--pack-out",
            str(pack),
            "--checklist-out",
            str(checklist),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(pack.read_text(encoding="utf-8"))
    assert data["requires_hidden_local_workspace_state"] is False
    assert data["requires_external_provider"] is False
    audit_data = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_data["official_certification_claimed"] is False
