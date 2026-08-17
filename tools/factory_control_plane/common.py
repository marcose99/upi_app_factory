from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any


PRODUCT_ID = "upi_app_factory"
PRODUCT_NAME = "UPI App Factory"
DEFAULT_BASELINE = "4df25fd0869bc59921ca438b89091349e5271997"


class ControlPlaneError(RuntimeError):
    """Raised when the control plane must fail closed."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ControlPlaneError(f"{path} must contain a JSON object")
    return {str(k): v for k, v in raw.items()}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def project_root_from(path: Path | None = None) -> Path:
    start = (path or Path.cwd()).resolve()
    cursor = start if start.is_dir() else start.parent
    for candidate in (cursor, *cursor.parents):
        if (candidate / ".git").exists():
            return candidate
    return cursor


def default_state_root(project_root: Path | None = None) -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_CONTROL_PLANE_STATE")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
    root = (base / PRODUCT_ID / "control_plane").resolve()
    if project_root is None:
        return root
    # Campaign ids are intentionally stable across clones. Keep their durable
    # lifecycle state local to one checkout without exposing its absolute path.
    checkout_id = sha256_text(str(project_root.resolve()))[:24]
    return root / "checkouts" / checkout_id


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ControlPlaneError(f"path escapes project root: {path}") from exc


def resolve_under_root(root: Path, value: str) -> Path:
    if "\x00" in value or "\n" in value:
        raise ControlPlaneError("path contains forbidden control data")
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ControlPlaneError(f"path escapes project root: {value}") from exc
    return candidate


def git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ControlPlaneError(completed.stderr.strip() or "git rev-parse failed")
    return completed.stdout.strip()


def git_worktree_identity(root: Path) -> dict[str, str]:
    """Identify candidate bytes plus index and validated filesystem modes."""
    paths = git_candidate_paths(root)
    index_modes = git_candidate_index_modes(root)
    digest = hashlib.sha256()
    for raw in paths:
        path = root / os.fsdecode(raw)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
        index_mode = index_modes.get(raw, b"UNTRACKED")
        digest.update(len(index_mode).to_bytes(8, "big"))
        digest.update(index_mode)
        if not os.path.lexists(path):
            digest.update(b"D")
            continue
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ControlPlaneError("candidate contains an unsafe evaluated input")
        payload = path.read_bytes()
        digest.update(b"F")
        digest.update(stat.S_IMODE(mode).to_bytes(4, "big"))
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return {"head": git_head(root), "tree_sha256": digest.hexdigest()}


def git_candidate_paths(root: Path) -> tuple[bytes, ...]:
    """Return the canonical tracked and untracked non-ignored candidate manifest."""
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ControlPlaneError(completed.stderr.decode(errors="replace").strip())
    return tuple(sorted(item for item in completed.stdout.split(b"\0") if item))


def git_candidate_index_modes(root: Path) -> dict[bytes, bytes]:
    """Return each tracked candidate path's exact Git index mode."""
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ControlPlaneError(completed.stderr.decode(errors="replace").strip())
    modes: dict[bytes, bytes] = {}
    for record in (item for item in completed.stdout.split(b"\0") if item):
        metadata, separator, raw = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[2] != b"0" or not raw:
            raise ControlPlaneError("git index contains an unsupported candidate entry")
        modes[raw] = fields[0]
    return modes


def ensure_no_forbidden_label(text: str) -> None:
    forbidden = "-".join(("autonomous", "control", "plane", "bootstrap", "v1"))
    if forbidden in text:
        raise ControlPlaneError("forbidden external workspace label detected")
