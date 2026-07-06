#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13J"
RUN_ID = "first_governed_generation_run_001"
BASELINE_TAG = "v0.13.8-release-readiness-operator-acceptance"
APP_WORKSPACE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DIR = APP_WORKSPACE / "lifecycle_artifacts" / "phase13j"
BUNDLE_DIR = APP_WORKSPACE / "release_handoff_bundle" / "phase13j"
PORTAL_PATH = APP_WORKSPACE / "audit_portal" / "factory_release_handoff_bundle_portal.html"
MANIFEST_PATH = PHASE_DIR / "release_handoff_bundle_manifest.json"
BUNDLE_MANIFEST_PATH = BUNDLE_DIR / "release_handoff_manifest.json"

EXPECTED_BUNDLE_FILES = [
    "release_handoff_manifest.json",
    "README.md",
    "OPERATOR_COMMANDS.md",
    "TRUTH_BOUNDARY.md",
    "CHECKSUMS.sha256",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 0


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"Missing JSON file: {path.relative_to(PROJECT_ROOT).as_posix()}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.relative_to(PROJECT_ROOT).as_posix()}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"Expected JSON object in {path.relative_to(PROJECT_ROOT).as_posix()}")
        return {}
    return payload


def validate_manifest(manifest: dict[str, Any], errors: list[str]) -> None:
    if manifest.get("phase") != PHASE:
        errors.append("Manifest phase mismatch.")
    if manifest.get("app_id") != APP_ID:
        errors.append("Manifest app_id mismatch.")
    if manifest.get("run_id") != RUN_ID:
        errors.append("Manifest run_id mismatch.")
    if manifest.get("baseline_tag") != BASELINE_TAG:
        errors.append("Manifest baseline_tag mismatch.")
    if not tag_exists(BASELINE_TAG):
        errors.append(f"Missing baseline tag: {BASELINE_TAG}")
    if manifest.get("errors"):
        errors.append("Manifest contains generation errors.")

    for entry in manifest.get("required_release_files", []):
        relative_path = entry.get("path")
        if not isinstance(relative_path, str):
            errors.append("Manifest contains a required file entry without a string path.")
            continue
        path = PROJECT_ROOT / relative_path
        if not path.is_file():
            errors.append(f"Missing required release file: {relative_path}")
            continue
        expected_sha = entry.get("sha256")
        actual_sha = sha256_file(path)
        if expected_sha != actual_sha:
            errors.append(f"Checksum mismatch for required release file: {relative_path}")


def validate_bundle_files(errors: list[str]) -> None:
    for relative_path in EXPECTED_BUNDLE_FILES:
        path = BUNDLE_DIR / relative_path
        if not path.is_file():
            errors.append(f"Missing bundle file: {path.relative_to(PROJECT_ROOT).as_posix()}")
    if not PORTAL_PATH.is_file():
        errors.append(f"Missing portal file: {PORTAL_PATH.relative_to(PROJECT_ROOT).as_posix()}")


def main() -> None:
    errors: list[str] = []
    manifest = load_json(MANIFEST_PATH, errors)
    bundle_manifest = load_json(BUNDLE_MANIFEST_PATH, errors)

    if manifest:
        validate_manifest(manifest, errors)
    if manifest and bundle_manifest and manifest != bundle_manifest:
        errors.append("Phase manifest and bundle manifest differ.")
    validate_bundle_files(errors)

    result = {
        "app_id": APP_ID,
        "baseline_tag": BASELINE_TAG,
        "bundle_directory": BUNDLE_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "errors": errors,
        "passed": not errors,
        "phase": PHASE,
        "run_id": RUN_ID,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
