#!/usr/bin/env python3
"""Build a deterministic clean-slate backup/restore plan.

This module is non-destructive. It inventories the generated application and
creates an auditable backup/restore plan for future clean-slate regeneration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


APP_ID = "upi_dispute_resolution"
DEFAULT_SOURCE = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")
DEFAULT_BACKUP_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/clean_slate_backups")
DEFAULT_LIFECYCLE_ARTIFACTS = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts"
)
DEFAULT_RELEASE_HANDOFF = Path("workspace/factory_generated/upi_dispute_resolution/release_handoff")


@dataclass(frozen=True)
class FileSnapshot:
    """One file in the generated application snapshot."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class BackupRestorePlan:
    """Non-destructive backup/restore plan for clean-slate regeneration."""

    app_id: str
    source_path: str
    backup_path: str
    restore_target_path: str
    source_exists: bool
    dry_run_only: bool
    destructive_delete_performed: bool
    backup_required_before_delete: bool
    restore_verification_required: bool
    evidence_preservation_paths: tuple[str, ...]
    file_count: int
    total_bytes: int
    manifest_digest: str
    files: tuple[FileSnapshot, ...]

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "backup_path": self.backup_path,
            "backup_required_before_delete": self.backup_required_before_delete,
            "destructive_delete_performed": self.destructive_delete_performed,
            "dry_run_only": self.dry_run_only,
            "evidence_preservation_paths": list(self.evidence_preservation_paths),
            "file_count": self.file_count,
            "files": [asdict(item) for item in self.files],
            "manifest_digest": self.manifest_digest,
            "restore_target_path": self.restore_target_path,
            "restore_verification_required": self.restore_verification_required,
            "schema_version": "clean-slate-backup-restore-plan.v1",
            "source_exists": self.source_exists,
            "source_path": self.source_path,
            "total_bytes": self.total_bytes,
        }


def _resolve_project_path(project_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def sha256_file(path: Path) -> str:
    """Return SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_snapshot_files(source: Path) -> Iterable[Path]:
    """Yield deterministic file list under source."""

    if not source.exists():
        return []

    files: list[Path] = []
    for candidate in source.rglob("*"):
        if not candidate.is_file():
            continue
        if "__pycache__" in candidate.parts:
            continue
        if candidate.suffix in {".pyc", ".pyo"}:
            continue
        files.append(candidate)

    return sorted(files, key=lambda item: item.as_posix())


def build_file_snapshots(source: Path) -> tuple[FileSnapshot, ...]:
    """Build deterministic file snapshots for source."""

    snapshots: list[FileSnapshot] = []
    for file_path in iter_snapshot_files(source):
        relative = file_path.relative_to(source).as_posix()
        snapshots.append(
            FileSnapshot(
                relative_path=relative,
                size_bytes=file_path.stat().st_size,
                sha256=sha256_file(file_path),
            )
        )
    return tuple(snapshots)


def manifest_digest(snapshots: tuple[FileSnapshot, ...]) -> str:
    """Build deterministic digest for a snapshot manifest."""

    payload = [
        {
            "relative_path": item.relative_path,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
        }
        for item in snapshots
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_backup_restore_plan(
    project_root: Path,
    source: Path = DEFAULT_SOURCE,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
) -> BackupRestorePlan:
    """Build a non-destructive clean-slate backup/restore plan."""

    root = project_root.resolve()
    source_path = _resolve_project_path(root, source)
    backup_root_path = _resolve_project_path(root, backup_root)
    backup_path = backup_root_path / "generated_application_snapshot"
    lifecycle_path = _resolve_project_path(root, DEFAULT_LIFECYCLE_ARTIFACTS)
    release_path = _resolve_project_path(root, DEFAULT_RELEASE_HANDOFF)

    snapshots = build_file_snapshots(source_path)
    total_bytes = sum(item.size_bytes for item in snapshots)

    return BackupRestorePlan(
        app_id=APP_ID,
        source_path=str(source_path),
        backup_path=str(backup_path),
        restore_target_path=str(source_path),
        source_exists=source_path.exists(),
        dry_run_only=True,
        destructive_delete_performed=False,
        backup_required_before_delete=True,
        restore_verification_required=True,
        evidence_preservation_paths=(str(lifecycle_path), str(release_path)),
        file_count=len(snapshots),
        total_bytes=total_bytes,
        manifest_digest=manifest_digest(snapshots),
        files=snapshots,
    )


def validate_backup_restore_plan(plan: BackupRestorePlan) -> list[str]:
    """Validate internal safety properties of a backup/restore plan."""

    failures: list[str] = []

    if not plan.dry_run_only:
        failures.append("Plan must be dry-run only in Phase 13AG")

    if plan.destructive_delete_performed:
        failures.append("Plan must not perform destructive delete")

    if not plan.backup_required_before_delete:
        failures.append("Backup must be required before delete")

    if not plan.restore_verification_required:
        failures.append("Restore verification must be required")

    if len(plan.evidence_preservation_paths) < 2:
        failures.append("Lifecycle and release evidence preservation paths are required")

    if len(plan.manifest_digest) != 64:
        failures.append("Manifest digest must be a SHA-256 hex digest")

    return failures


def write_audit_plan(plan: BackupRestorePlan, audit_out: Path) -> None:
    """Write deterministic JSON audit for a backup/restore plan."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build clean-slate backup/restore plan.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    plan = build_backup_restore_plan(args.project_root, args.source, args.backup_root)

    if args.audit_out is not None:
        write_audit_plan(plan, args.audit_out)

    print(json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_backup_restore_plan(plan)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
