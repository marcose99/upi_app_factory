#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = (
    PROJECT_ROOT
    / "factory_governance"
    / "clean_clone_test_evidence"
)
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
DEFAULT_TARGET_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Manifest root must be a JSON object")
    return cast(dict[str, Any], value)


def safe_relative(value: object, field_name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")

    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a safe relative path")

    return path


def bootstrap(target_root: Path) -> dict[str, Any]:
    manifest = load_manifest()
    raw_files = manifest.get("files")

    if manifest.get("fixture_count") != 18:
        raise ValueError("Manifest fixture_count must be 18")
    if manifest.get("normalization_count") != 8:
        raise ValueError("Manifest normalization_count must be 8")
    if not isinstance(raw_files, list):
        raise ValueError("Manifest files must be a JSON array")

    copied: list[str] = []
    existing: list[str] = []
    errors: list[str] = []

    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            errors.append("invalid_manifest_entry")
            continue

        entry = cast(dict[str, Any], raw_entry)

        try:
            fixture_relative = safe_relative(
                entry.get("fixture_relative_path"),
                "fixture_relative_path",
            )
            target_relative = safe_relative(
                entry.get("target_relative_path"),
                "target_relative_path",
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        expected_sha = entry.get("fixture_sha256")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            errors.append(f"invalid_sha256:{fixture_relative}")
            continue

        source = FIXTURE_ROOT / fixture_relative
        destination = target_root / target_relative

        if not source.is_file():
            errors.append(f"missing_fixture:{fixture_relative}")
            continue

        if sha256_path(source) != expected_sha:
            errors.append(f"fixture_checksum_mismatch:{fixture_relative}")
            continue

        if destination.exists():
            if not destination.is_file():
                errors.append(f"destination_not_file:{target_relative}")
                continue

            if sha256_path(destination) != expected_sha:
                errors.append(
                    f"destination_checksum_mismatch:{target_relative}"
                )
                continue

            existing.append(target_relative.as_posix())
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

        if sha256_path(destination) != expected_sha:
            errors.append(f"copied_checksum_mismatch:{target_relative}")
            continue

        copied.append(target_relative.as_posix())

    return {
        "status": "FAILED" if errors else "PASSED",
        "target_root": str(target_root),
        "files_declared": len(raw_files),
        "files_copied": len(copied),
        "files_existing": len(existing),
        "errors": errors,
        "llm_calls": 0,
        "real_payment_calls": "disabled",
        "official_certification_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize deterministic lifecycle evidence required by "
            "clean-clone tests."
        )
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        default=DEFAULT_TARGET_ROOT,
    )
    args = parser.parse_args()

    try:
        result = bootstrap(args.target_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "status": "FAILED",
            "errors": [f"{type(exc).__name__}:{exc}"],
            "llm_calls": 0,
            "real_payment_calls": "disabled",
            "official_certification_claimed": False,
        }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
