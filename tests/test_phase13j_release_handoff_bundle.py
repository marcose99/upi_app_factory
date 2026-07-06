from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
APP_WORKSPACE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DIR = APP_WORKSPACE / "lifecycle_artifacts" / "phase13j"
BUNDLE_DIR = APP_WORKSPACE / "release_handoff_bundle" / "phase13j"
MANIFEST_PATH = PHASE_DIR / "release_handoff_bundle_manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_release_handoff_manifest_exists_and_passes() -> None:
    manifest = load_manifest()
    assert manifest["phase"] == "Phase 13J"
    assert manifest["app_id"] == APP_ID
    assert manifest["baseline_tag"] == "v0.13.8-release-readiness-operator-acceptance"
    assert manifest["passed"] is True
    assert manifest["errors"] == []


def test_release_handoff_bundle_files_exist() -> None:
    expected_files = [
        "release_handoff_manifest.json",
        "README.md",
        "OPERATOR_COMMANDS.md",
        "TRUTH_BOUNDARY.md",
        "CHECKSUMS.sha256",
    ]
    for relative_path in expected_files:
        assert (BUNDLE_DIR / relative_path).is_file()


def test_phase13j_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13j_release_handoff_bundle.py"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["errors"] == []
