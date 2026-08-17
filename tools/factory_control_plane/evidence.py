from __future__ import annotations

import hashlib
import gzip
import io
import json
import os
import stat
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from tools.factory_control_plane.common import ControlPlaneError, sha256_bytes
from tools.factory_control_plane.fs_guard import FilesystemGuard, _rename_noreplace
from tools.factory_control_plane.state import StateStore


def campaign_evidence_dir(state_root: Path, campaign_id: str) -> Path:
    return state_root / "evidence" / campaign_id


def write_activity_envelope(root: Path, campaign_id: str, activity_id: str, payload: dict[str, Any]) -> Path:
    path = campaign_evidence_dir(root, campaign_id) / "activities" / f"{activity_id}.json"
    _write_json_under_root(root, path, payload)
    return path


def write_control_envelope(root: Path, campaign_id: str, phase: str, payload: dict[str, Any]) -> Path:
    path = campaign_evidence_dir(root, campaign_id) / "control" / f"{phase}.json"
    _write_json_under_root(root, path, payload)
    return path


def write_summary(root: Path, store: StateStore, campaign_id: str) -> Path:
    path = campaign_evidence_dir(root, campaign_id) / "summary.json"
    _write_json_under_root(
        root,
        path,
        {"summary": store.summary(campaign_id), "events": store.export_events(campaign_id)},
    )
    return path


def _write_json_under_root(root: Path, path: Path, payload: object) -> None:
    guard = FilesystemGuard(root)
    try:
        relative = path.relative_to(root).as_posix()
        guard.write_text(relative, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    finally:
        guard.close()


def _snapshot(source: Path) -> dict[str, tuple[bytes, int]]:
    captured: dict[str, tuple[bytes, int]] = {}
    root_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(root_fd)
        _snapshot_directory(root_fd, (), captured)
        if _stat_identity(before) != _stat_identity(os.fstat(root_fd)):
            raise ControlPlaneError("evidence root mutated while sealing")
    finally:
        os.close(root_fd)
    return dict(sorted(captured.items()))


def snapshot_manifest(source: Path) -> dict[str, str]:
    """Build a descriptor-bound manifest and reject unsafe or racing entries."""
    return {
        name: sha256_bytes(payload)
        for name, (payload, _mode) in _snapshot(source.resolve(strict=True)).items()
    }


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
        value.st_size, value.st_mtime_ns, value.st_ctime_ns,
    )


def _snapshot_directory(
    directory_fd: int,
    relative_parts: tuple[str, ...],
    captured: dict[str, tuple[bytes, int]],
) -> None:
    directory_before = os.fstat(directory_fd)
    if not stat.S_ISDIR(directory_before.st_mode):
        raise ControlPlaneError("refusing to seal non-directory")
    for name in sorted(os.listdir(directory_fd)):
        relative_parts_child = (*relative_parts, name)
        relative = Path(*relative_parts_child).as_posix()
        entry_before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(entry_before.st_mode):
            child_fd = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            try:
                if _stat_identity(entry_before) != _stat_identity(os.fstat(child_fd)):
                    raise ControlPlaneError(f"evidence directory changed: {relative}")
                _snapshot_directory(child_fd, relative_parts_child, captured)
                entry_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if _stat_identity(entry_before) != _stat_identity(entry_after):
                    raise ControlPlaneError(f"evidence directory mutated: {relative}")
            finally:
                os.close(child_fd)
            continue
        if stat.S_ISLNK(entry_before.st_mode):
            raise ControlPlaneError(f"refusing to seal symlink: {relative}")
        if not stat.S_ISREG(entry_before.st_mode) or entry_before.st_nlink != 1:
            raise ControlPlaneError(f"refusing to seal unsafe file: {relative}")
        file_fd = os.open(
            name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd
        )
        try:
            opened = os.fstat(file_fd)
            if _stat_identity(entry_before) != _stat_identity(opened):
                raise ControlPlaneError(f"evidence file changed: {relative}")
            chunks: list[bytes] = []
            while chunk := os.read(file_fd, 1024 * 1024):
                chunks.append(chunk)
            after = os.fstat(file_fd)
            current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if _stat_identity(opened) != _stat_identity(after) or _stat_identity(after) != _stat_identity(current):
                raise ControlPlaneError(f"evidence mutated while sealing: {relative}")
            captured[relative] = (b"".join(chunks), stat.S_IMODE(opened.st_mode))
        finally:
            os.close(file_fd)
    if _stat_identity(directory_before) != _stat_identity(os.fstat(directory_fd)):
        raise ControlPlaneError("evidence directory mutated while sealing")


def _atomic_write(path: Path, payload: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _publish_anchor(anchor_path: Path, payload: bytes) -> None:
    """Publish once outside campaign state; allow only byte-identical retries."""
    if anchor_path.exists():
        if anchor_path.is_file() and anchor_path.read_bytes() == payload:
            return
        raise ControlPlaneError("detached evidence trust anchor already exists")
    fd, temporary = tempfile.mkstemp(
        prefix=f".{anchor_path.name}.", dir=anchor_path.parent
    )
    os.close(fd)
    staged = Path(temporary)
    try:
        _atomic_write(staged, payload)
        anchor_fd = os.open(
            anchor_path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        )
        try:
            _rename_noreplace(staged.name, anchor_path.name, anchor_fd, anchor_fd)
            os.fsync(anchor_fd)
        finally:
            os.close(anchor_fd)
    finally:
        staged.unlink(missing_ok=True)


def seal_directory(
    source: Path, output_dir: Path, anchor_dir: Path
) -> dict[str, str]:
    source = source.resolve(strict=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    anchor_dir = anchor_dir.resolve()
    if anchor_dir == output_dir.resolve() or anchor_dir.is_relative_to(output_dir.resolve()):
        raise ControlPlaneError("evidence trust anchors must be outside the seal publication root")
    anchor_dir.mkdir(parents=True, exist_ok=True)
    captured = _snapshot(source)
    manifest = {name: sha256_bytes(payload) for name, (payload, _mode) in captured.items()}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    archive_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=archive_buffer, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w:") as archive:
            for name, (payload, mode) in captured.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(payload), mode, 0
                archive.addfile(info, io.BytesIO(payload))
    archive_bytes = archive_buffer.getvalue()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        verified: dict[str, str] = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is None:
                    raise ControlPlaneError("completed evidence archive is unreadable")
                verified[member.name] = hashlib.sha256(stream.read()).hexdigest()
    if verified != manifest:
        raise ControlPlaneError("completed evidence archive does not match its manifest")
    publication = output_dir / f"{source.name}.seal"
    if publication.exists():
        raise ControlPlaneError("evidence seal publication already exists")
    staging = Path(tempfile.mkdtemp(prefix=f".{source.name}.seal.", dir=output_dir))
    manifest_path = staging / f"{source.name}.manifest.json"
    archive_path = staging / f"{source.name}.tar.gz"
    checksum_path = staging / f"{source.name}.tar.gz.sha256"
    anchor_path = anchor_dir / f"{source.name}.anchor.json"
    archive_hash = sha256_bytes(archive_bytes)
    manifest_hash = sha256_bytes(manifest_bytes)
    try:
        _atomic_write(manifest_path, manifest_bytes)
        _atomic_write(archive_path, archive_bytes)
        _atomic_write(checksum_path, (
            f"{manifest_hash}  {manifest_path.name}\n"
            f"{archive_hash}  {archive_path.name}\n"
        ).encode())
        anchor_payload = (json.dumps({
            "archive_sha256": archive_hash,
            "manifest_sha256": manifest_hash,
            "seal": source.name,
        }, indent=2, sort_keys=True) + "\n").encode()
        _publish_anchor(anchor_path, anchor_payload)
        directory_fd = os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory_fd)
            _rename_noreplace(staging.name, publication.name, directory_fd, directory_fd)
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        for path in (manifest_path, archive_path, checksum_path):
            path.unlink(missing_ok=True)
        try:
            staging.rmdir()
        except FileNotFoundError:
            pass
        raise
    manifest_path = publication / manifest_path.name
    archive_path = publication / archive_path.name
    checksum_path = publication / checksum_path.name
    return verify_seal(manifest_path, archive_path, checksum_path, anchor_path)


def verify_seal(
    manifest_path: Path,
    archive_path: Path,
    checksum_path: Path,
    anchor_path: Path,
) -> dict[str, str]:
    """Fail closed unless the seal agrees with its detached trust anchor."""
    if not all(
        path.is_file()
        for path in (manifest_path, archive_path, checksum_path, anchor_path)
    ):
        raise ControlPlaneError("closed campaign seal is missing")
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict) or not all(
            isinstance(name, str) and isinstance(digest, str)
            for name, digest in manifest.items()
        ):
            raise ValueError("invalid manifest")
        archive_bytes = archive_path.read_bytes()
        archive_hash = sha256_bytes(archive_bytes)
        manifest_hash = sha256_bytes(manifest_bytes)
        expected_checksums = (
            f"{manifest_hash}  {manifest_path.name}\n"
            f"{archive_hash}  {archive_path.name}\n"
        )
        if checksum_path.read_text(encoding="ascii") != expected_checksums:
            raise ValueError("checksum mismatch")
        anchor = json.loads(anchor_path.read_bytes())
        if anchor != {
            "archive_sha256": archive_hash,
            "manifest_sha256": manifest_hash,
            "seal": manifest_path.name.removesuffix(".manifest.json"),
        }:
            raise ValueError("detached trust anchor mismatch")
        verified: dict[str, str] = {}
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if (
                    not member.isfile()
                    or path.is_absolute()
                    or ".." in path.parts
                    or member.name in verified
                ):
                    raise ValueError("unsafe archive membership")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("unreadable archive member")
                verified[member.name] = hashlib.sha256(stream.read()).hexdigest()
        if verified != manifest:
            raise ValueError("archive does not match manifest")
    except (OSError, UnicodeError, json.JSONDecodeError, tarfile.TarError, ValueError) as exc:
        raise ControlPlaneError("closed campaign seal failed integrity validation") from exc
    return {
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "archive": str(archive_path),
        "archive_sha256": archive_hash,
        "checksum": str(checksum_path),
        "anchor": str(anchor_path),
    }
