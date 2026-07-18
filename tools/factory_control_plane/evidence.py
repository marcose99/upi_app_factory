from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

from tools.factory_control_plane.common import ControlPlaneError, sha256_file, write_json
from tools.factory_control_plane.state import StateStore


def campaign_evidence_dir(state_root: Path, campaign_id: str) -> Path:
    safe = campaign_id.replace("/", "_")
    return state_root / "evidence" / safe


def write_activity_envelope(
    root: Path,
    campaign_id: str,
    activity_id: str,
    payload: dict[str, Any],
) -> Path:
    path = campaign_evidence_dir(root, campaign_id) / "activities" / f"{activity_id}.json"
    write_json(path, payload)
    return path


def write_control_envelope(
    root: Path,
    campaign_id: str,
    phase: str,
    payload: dict[str, Any],
) -> Path:
    path = campaign_evidence_dir(root, campaign_id) / "control" / f"{phase}.json"
    write_json(path, payload)
    return path


def write_summary(root: Path, store: StateStore, campaign_id: str) -> Path:
    path = campaign_evidence_dir(root, campaign_id) / "summary.json"
    write_json(
        path,
        {
            "summary": store.summary(campaign_id),
            "events": store.export_events(campaign_id),
        },
    )
    return path


def seal_directory(source: Path, output_dir: Path) -> dict[str, str]:
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ControlPlaneError(f"refusing to seal symlink: {path}")
    manifest: dict[str, str] = {}
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        manifest[path.relative_to(source).as_posix()] = sha256_file(path)
    manifest_path = output_dir / f"{source.name}.manifest.json"
    write_json(manifest_path, manifest)
    archive_path = output_dir / f"{source.name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            archive.add(
                path,
                arcname=path.relative_to(source).as_posix(),
                recursive=False,
            )
    checksum_path = output_dir / f"{source.name}.tar.gz.sha256"
    checksum_path.write_text(
        sha256_file(archive_path) + "  " + archive_path.name + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "archive": str(archive_path),
        "archive_sha256": sha256_file(archive_path),
        "checksum": str(checksum_path),
    }
