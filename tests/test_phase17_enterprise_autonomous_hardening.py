from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_phase17_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase17_enterprise_autonomous_hardening.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase17_tmp_evidence_preserves_certification_boundary(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    dossier = tmp_path / "dossier.json"
    reviewer = tmp_path / "reviewer.json"
    backlog = tmp_path / "backlog.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase17_enterprise_autonomous_hardening.py",
            "--audit-out",
            str(audit),
            "--dossier-out",
            str(dossier),
            "--reviewer-out",
            str(reviewer),
            "--backlog-out",
            str(backlog),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(audit.read_text(encoding="utf-8"))
    assert data["factory_does_not_self_certify"] is True
    assert data["official_certification_claimed"] is False
    assert data["live_provider_calls_performed"] is False
