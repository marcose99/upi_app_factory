from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/bootstrap_clean_clone_test_evidence.py"
FIXTURE_ROOT = (
    ROOT
    / "factory_governance"
    / "clean_clone_test_evidence"
)


def run_bootstrap(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--target-root",
            str(target),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def load_output(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    value = json.loads(result.stdout)
    return cast(dict[str, Any], value)


def test_fixture_manifest_records_bounded_normalization() -> None:
    manifest = json.loads(
        (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["fixture_count"] == 18
    assert manifest["normalization_count"] == 8
    assert len(manifest["files"]) == 18
    assert len(manifest["normalizations"]) == 8


def test_fixture_tree_contains_no_local_home_paths_or_retired_identity() -> None:
    retired_identity = "upi_dispute_resolution" + "_factory"
    prohibited_project_label = "Factory" + "FromNothing"

    for path in sorted((FIXTURE_ROOT / "files").rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert "/home/" not in text
        assert retired_identity not in text
        assert prohibited_project_label not in text


def test_bootstrap_materializes_all_declared_evidence(
    tmp_path: Path,
) -> None:
    target = tmp_path / "lifecycle_artifacts"

    result = run_bootstrap(target)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = load_output(result)
    assert payload["status"] == "PASSED"
    assert payload["files_declared"] == 18
    assert payload["files_copied"] == 18
    assert payload["files_existing"] == 0


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "lifecycle_artifacts"

    first = run_bootstrap(target)
    second = run_bootstrap(target)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr

    payload = load_output(second)
    assert payload["status"] == "PASSED"
    assert payload["files_copied"] == 0
    assert payload["files_existing"] == 18


def test_bootstrap_fails_closed_on_conflicting_destination(
    tmp_path: Path,
) -> None:
    target = tmp_path / "lifecycle_artifacts"

    first = run_bootstrap(target)
    assert first.returncode == 0, first.stdout + first.stderr

    destination = next(target.rglob("*.json"))
    destination.write_text("{}\n", encoding="utf-8")

    second = run_bootstrap(target)

    assert second.returncode != 0
    payload = load_output(second)
    assert payload["status"] == "FAILED"
    assert any(
        str(error).startswith("destination_checksum_mismatch:")
        for error in payload["errors"]
    )
