from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+91[- ]?)?[6-9]\d{9}\b")
UPI_RE = re.compile(r"\b[A-Z0-9._-]+@[A-Z][A-Z0-9._-]+\b", re.IGNORECASE)
SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|OPENAI_API_KEY\s*=\s*\S+|api[_-]?key\s*[:=]\s*\S+)\b", re.IGNORECASE)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def redact(value: str) -> str:
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = UPI_RE.sub("[REDACTED_UPI]", redacted)
    return SECRET_RE.sub("[REDACTED_SECRET]", redacted)


def contains_sensitive(value: str) -> bool:
    return any(pattern.search(value) for pattern in (EMAIL_RE, PHONE_RE, UPI_RE, SECRET_RE))


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def safe_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
