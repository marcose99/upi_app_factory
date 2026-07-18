from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
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


def default_state_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_CONTROL_PLANE_STATE")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.cwd() / ".control_plane_state"
    return (base / PRODUCT_ID / "control_plane").resolve()


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


def ensure_no_forbidden_label(text: str) -> None:
    forbidden = "-".join(("autonomous", "control", "plane", "bootstrap", "v1"))
    if forbidden in text:
        raise ControlPlaneError("forbidden external workspace label detected")
