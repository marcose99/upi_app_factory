from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase13k" / "release_handoff_replay_audit.json"


def test_phase13k_audit_passes() -> None:
    data = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert data["passed"] is True
    assert data["errors"] == []
    assert data["checksum_scope"] == "repository_root"
    assert data["baseline_tag_present"] is True


def test_phase13k_checksum_entries_are_repository_root_scoped() -> None:
    data = json.loads(AUDIT.read_text(encoding="utf-8"))
    entries = data["checksum_entries"]
    assert entries
    assert all(entry["scope"] == "repository_root" for entry in entries)
    assert all(entry["exists"] for entry in entries)
    assert all(entry["matches"] for entry in entries)


def test_phase13k_validator_passes() -> None:
    result = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python3"), "scripts/validate_phase13k_release_handoff_replay.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
