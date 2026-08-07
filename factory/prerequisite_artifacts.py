from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Collection, Mapping, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEAN_CLONE_FIXTURE_ROOT = (
    PROJECT_ROOT
    / "factory_governance"
    / "clean_clone_test_evidence"
)
CLEAN_CLONE_MANIFEST_PATH = CLEAN_CLONE_FIXTURE_ROOT / "manifest.json"
DEFAULT_LIFECYCLE_ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
)
DEFAULT_MUTABLE_TEST_ROOTS = (
    "workspace/deep_engineering_campaign",
    "workspace/factory_generated/phase51_portfolio_e2e_tests",
    "workspace/factory_generated/phase51_test_roots",
    "workspace/factory_generated/post_r9_5",
    "workspace/factory_generated/portal_external_state_tests",
    "workspace/factory_generated/upi_dispute_resolution/audit_portal",
    "workspace/factory_generated/upi_dispute_resolution/export_bundles",
    "workspace/factory_generated/upi_dispute_resolution/generation_runs",
    "workspace/factory_generated/upi_dispute_resolution/identity_test_roots",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts",
    "workspace/factory_generated/upi_dispute_resolution/operator_handoff",
    "workspace/factory_generated/upi_dispute_resolution/phase51_identity_test_portfolio",
    "workspace/factory_generated/upi_dispute_resolution/portal_publications",
    "workspace/tmp",
    "factory_governance/phase68_70/recipient_replay_output",
)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: object, *, field_name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a safe relative path")
    return path


def _load_clean_clone_manifest(project_root: Path) -> dict[str, Any]:
    manifest_path = project_root / CLEAN_CLONE_MANIFEST_PATH.relative_to(PROJECT_ROOT)
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("clean-clone evidence manifest must be a JSON object")
    manifest = cast(dict[str, Any], value)
    if manifest.get("fixture_count") != 18:
        raise ValueError("clean-clone evidence manifest fixture_count must be 18")
    if manifest.get("normalization_count") != 8:
        raise ValueError("clean-clone evidence manifest normalization_count must be 8")
    return manifest


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def _prune_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path.parent
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def snapshot_mutable_test_roots(
    project_root: Path | None = None,
    *,
    relative_paths: Collection[str] | None = None,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    snapshot_directory = (snapshot_root or Path(tempfile.mkdtemp(prefix="upi_app_factory_pytest_snapshot_"))).resolve()
    entries: list[dict[str, Any]] = []
    errors: list[str] = []

    for raw_relative in relative_paths or DEFAULT_MUTABLE_TEST_ROOTS:
        relative = _safe_relative(raw_relative, field_name="relative_path")
        source = root / relative
        backup = snapshot_directory / relative
        entry: dict[str, Any] = {
            "relative_path": relative.as_posix(),
            "snapshot_path": str(backup),
        }

        if source.is_symlink():
            errors.append(f"mutable_root_symlink:{relative.as_posix()}")
            entries.append({**entry, "kind": "unsupported"})
            continue
        if not source.exists():
            entries.append({**entry, "kind": "missing"})
            continue
        if source.is_file():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, backup)
            entries.append({**entry, "kind": "file", "size_bytes": source.stat().st_size})
            continue
        if source.is_dir():
            shutil.copytree(source, backup, symlinks=False)
            file_count = sum(1 for path in source.rglob("*") if path.is_file())
            entries.append({**entry, "kind": "directory", "file_count": file_count})
            continue
        errors.append(f"mutable_root_unsupported:{relative.as_posix()}")
        entries.append({**entry, "kind": "unsupported"})

    return {
        "status": "FAILED" if errors else "SNAPSHOTTED",
        "project_root": str(root),
        "snapshot_root": str(snapshot_directory),
        "entries": entries,
        "errors": errors,
    }


def restore_mutable_test_roots(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    project_root = Path(str(snapshot["project_root"])).resolve()
    snapshot_root = Path(str(snapshot["snapshot_root"])).resolve()
    raw_entries = snapshot.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("snapshot entries must be a list")

    restored: list[str] = []
    removed: list[str] = []
    errors: list[str] = []

    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            errors.append("invalid_snapshot_entry")
            continue
        entry = cast(dict[str, Any], raw_entry)
        relative = _safe_relative(entry.get("relative_path"), field_name="relative_path")
        kind = entry.get("kind")
        target = project_root / relative
        backup = snapshot_root / relative

        if target.is_symlink():
            errors.append(f"mutable_root_symlink:{relative.as_posix()}")
            continue

        _remove_path(target)

        if kind == "missing":
            removed.append(relative.as_posix())
            _prune_empty_parents(target, stop_at=project_root)
            continue
        if kind == "file":
            if not backup.is_file():
                errors.append(f"snapshot_missing_file:{relative.as_posix()}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(backup, target)
            restored.append(relative.as_posix())
            continue
        if kind == "directory":
            if not backup.is_dir():
                errors.append(f"snapshot_missing_directory:{relative.as_posix()}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(backup, target, symlinks=False)
            restored.append(relative.as_posix())
            continue
        errors.append(f"unsupported_snapshot_kind:{relative.as_posix()}")

    shutil.rmtree(snapshot_root, ignore_errors=True)

    return {
        "status": "FAILED" if errors else "RESTORED",
        "project_root": str(project_root),
        "restored_paths": restored,
        "removed_paths": removed,
        "errors": errors,
    }


def materialize_clean_clone_test_evidence(
    project_root: Path | None = None,
    *,
    target_root: Path | None = None,
    include_phases: Collection[str] | None = None,
) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    destination_root = (target_root or (root / DEFAULT_LIFECYCLE_ARTIFACT_ROOT.relative_to(PROJECT_ROOT))).resolve()
    fixture_root = root / CLEAN_CLONE_FIXTURE_ROOT.relative_to(PROJECT_ROOT)
    manifest = _load_clean_clone_manifest(root)
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise ValueError("clean-clone evidence manifest files must be a JSON array")

    requested_phases = {phase for phase in include_phases or () if phase}
    copied: list[str] = []
    existing: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    selected_entries = 0

    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            errors.append("invalid_manifest_entry")
            continue
        entry = cast(dict[str, Any], raw_entry)
        fixture_relative = _safe_relative(
            entry.get("fixture_relative_path"),
            field_name="fixture_relative_path",
        )
        target_relative = _safe_relative(
            entry.get("target_relative_path"),
            field_name="target_relative_path",
        )
        if requested_phases and (
            not target_relative.parts or target_relative.parts[0] not in requested_phases
        ):
            skipped.append(target_relative.as_posix())
            continue

        selected_entries += 1
        expected_sha = entry.get("fixture_sha256")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            errors.append(f"invalid_sha256:{fixture_relative.as_posix()}")
            continue

        source = fixture_root / fixture_relative
        destination = destination_root / target_relative
        if not source.is_file():
            errors.append(f"missing_fixture:{fixture_relative.as_posix()}")
            continue
        if _sha256_path(source) != expected_sha:
            errors.append(f"fixture_checksum_mismatch:{fixture_relative.as_posix()}")
            continue
        if destination.exists():
            if not destination.is_file():
                errors.append(f"destination_not_file:{target_relative.as_posix()}")
                continue
            if _sha256_path(destination) != expected_sha:
                errors.append(f"destination_checksum_mismatch:{target_relative.as_posix()}")
                continue
            existing.append(target_relative.as_posix())
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if _sha256_path(destination) != expected_sha:
            errors.append(f"copied_checksum_mismatch:{target_relative.as_posix()}")
            continue
        copied.append(target_relative.as_posix())

    return {
        "status": "FAILED" if errors else "PASSED",
        "target_root": str(destination_root),
        "files_declared": selected_entries,
        "files_copied": len(copied),
        "files_existing": len(existing),
        "files_skipped": len(skipped),
        "copied_paths": copied,
        "existing_paths": existing,
        "errors": errors,
        "llm_calls": 0,
        "real_payment_calls": "disabled",
        "official_certification_claimed": False,
    }
