from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def capture_files(
    root: Path,
    relative_paths: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for relative in relative_paths:
        path = root / relative
        snapshot[relative] = {
            "exists": path.exists(),
            "content_base64": (
                base64.b64encode(path.read_bytes()).decode("ascii") if path.is_file() else None
            ),
        }
    return snapshot


def restore_files(root: Path, snapshot: dict[str, dict[str, Any]]) -> None:
    for relative, record in snapshot.items():
        path = root / relative
        if record.get("exists") is True:
            encoded = record.get("content_base64")
            if not isinstance(encoded, str):
                raise ValueError(f"Snapshot content missing: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(encoded))
        elif path.exists():
            path.unlink()
