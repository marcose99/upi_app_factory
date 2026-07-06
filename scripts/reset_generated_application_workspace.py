#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DEFAULT_RUN_ID = "first_governed_generation_run_001"
FACTORY_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
GENERATED_APP = FACTORY_ROOT / "generated_application"
ARCHIVES = FACTORY_ROOT / "generated_application_archives"
GENERATION_RUNS = FACTORY_ROOT / "generation_runs"


def kolkata_now() -> datetime:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Kolkata"))
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def timestamp_ist() -> str:
    return kolkata_now().strftime("%Y%m%d_%H%M%S_IST")


def ensure_safe_path(path: Path) -> None:
    resolved = path.resolve()
    expected = GENERATED_APP.resolve()
    if resolved != expected:
        raise RuntimeError(f"Unsafe reset target: expected {expected}, got {resolved}")
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError(f"Reset target is outside project root: {resolved}")


def snapshot_paths(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(str(child.relative_to(path)) for child in path.rglob("*"))


def recreate_skeleton(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for rel in ["app", "tests", "docs", "evidence"]:
        (path / rel).mkdir(parents=True, exist_ok=True)
        (path / rel / ".gitkeep").write_text("", encoding="utf-8")

    (path / "README.md").write_text(
        "# Generated UPI Dispute Resolution Application\n\n"
        "This workspace is intentionally resettable. The generated application can be "
        "deleted and recreated by the governed factory reset script.\n\n"
        "Boundary: the primary application is locally runnable; external NPCI/RBI/"
        "bank/PSP/ODR/payment-rail ecosystem integrations remain mock/simulated.\n",
        encoding="utf-8",
    )


def write_manifest(
    *,
    run_id: str,
    mode: str,
    archive_path: Path | None,
    before_paths: list[str],
    after_paths: list[str],
    dry_run: bool,
) -> Path:
    manifest_dir = GENERATION_RUNS / run_id / "reset_manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{timestamp_ist()}_generated_application_reset_manifest.json"
    manifest: dict[str, Any] = {
        "app_id": APP_ID,
        "run_id": run_id,
        "mode": mode,
        "dry_run": dry_run,
        "target": str(GENERATED_APP.relative_to(ROOT)),
        "archive_path": str(archive_path.relative_to(ROOT)) if archive_path else None,
        "before_path_count": len(before_paths),
        "after_path_count": len(after_paths),
        "before_paths_sample": before_paths[:50],
        "after_paths": after_paths,
        "protected_paths": [
            "docs",
            "factory_governance",
            "prompts",
            "scripts",
            "src",
            "tests",
            "workspace/run_logs",
            f"workspace/factory_generated/{APP_ID}/lifecycle_artifacts",
            f"workspace/factory_generated/{APP_ID}/generation_runs",
            f"workspace/factory_generated/{APP_ID}/audit_portal",
        ],
        "timestamp_ist": kolkata_now().isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def reset_generated_application(*, run_id: str, no_archive: bool, dry_run: bool) -> dict[str, Any]:
    ensure_safe_path(GENERATED_APP)
    before_paths = snapshot_paths(GENERATED_APP)
    archive_path: Path | None = None

    if dry_run:
        after_paths = ["README.md", "app/.gitkeep", "docs/.gitkeep", "evidence/.gitkeep", "tests/.gitkeep"]
        manifest_path = write_manifest(
            run_id=run_id,
            mode="dry_run",
            archive_path=None,
            before_paths=before_paths,
            after_paths=after_paths,
            dry_run=True,
        )
        return {
            "dry_run": True,
            "target": str(GENERATED_APP.relative_to(ROOT)),
            "before_path_count": len(before_paths),
            "manifest": str(manifest_path.relative_to(ROOT)),
        }

    if GENERATED_APP.exists() and before_paths and not no_archive:
        ARCHIVES.mkdir(parents=True, exist_ok=True)
        archive_path = ARCHIVES / f"{timestamp_ist()}_generated_application"
        shutil.copytree(GENERATED_APP, archive_path)

    if GENERATED_APP.exists():
        shutil.rmtree(GENERATED_APP)

    recreate_skeleton(GENERATED_APP)
    after_paths = snapshot_paths(GENERATED_APP)

    manifest_path = write_manifest(
        run_id=run_id,
        mode="delete_recreate",
        archive_path=archive_path,
        before_paths=before_paths,
        after_paths=after_paths,
        dry_run=False,
    )

    return {
        "dry_run": False,
        "target": str(GENERATED_APP.relative_to(ROOT)),
        "archive_path": str(archive_path.relative_to(ROOT)) if archive_path else None,
        "before_path_count": len(before_paths),
        "after_path_count": len(after_paths),
        "manifest": str(manifest_path.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely delete and recreate the generated application workspace.")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-archive", action="store_true", help="Delete without first archiving generated_application.")
    parser.add_argument("--dry-run", action="store_true", help="Only write a dry-run manifest; do not delete or recreate.")
    args = parser.parse_args()

    result = reset_generated_application(
        run_id=args.run_id,
        no_archive=args.no_archive,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
