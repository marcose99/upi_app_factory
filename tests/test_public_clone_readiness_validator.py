from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_public_clone_readiness import validate


def test_public_clone_readiness_validator_passes_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    report = validate(root, "Apache-2.0")
    assert report["status"] == "passed", json.dumps(report, indent=2)
    check_names = {check["name"] for check in report["checks"]}
    assert {
        "license_notice",
        "personal_paths_and_stale_identities",
        "tracked_workspace_state_policy",
        "openapi_and_test_evidence_hooks",
        "secrets",
    } <= check_names


def test_public_clone_readiness_cli_writes_json_output(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "public-readiness.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validate_public_clone_readiness.py"),
            "--repo",
            str(root),
            "--license",
            "Apache-2.0",
            "--json-output",
            str(output),
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "passed"


def test_public_clone_readiness_fails_closed_outside_git(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validate_public_clone_readiness.py"),
            "--repo",
            str(tmp_path),
            "--license",
            "Apache-2.0",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode != 0
    assert '"status": "failed"' in completed.stdout
    assert "fail_closed" in completed.stdout
