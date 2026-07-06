from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase13h" / "release_state_snapshot.json"


def test_phase13h_snapshot_is_deterministic_and_truthful() -> None:
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert payload["phase"] == "Phase 13H"
    assert payload["passed"] is True
    assert payload["evidence_determinism"]["uses_wall_clock_timestamp"] is False
    assert payload["evidence_determinism"]["uses_current_commit_hash"] is False
    assert "LangGraph/OpenAI" in payload["truth_boundary"]
    assert "policy-gated" in payload["truth_boundary"]


def test_phase13h_release_lineage_contains_phase13g_baseline() -> None:
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    tags = {item["tag"] for item in payload["release_lineage"]}
    assert "v0.13.6-readonly-validation-drift-guardrails" in tags
    assert all(item["tag_present"] for item in payload["release_lineage"])


def test_phase13h_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_phase13h_release_state_lineage.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert '"passed": true' in result.stdout
