"""Shared errors and bounded validation helpers for architecture decisioning."""

from __future__ import annotations

import re
from typing import Any


class ArchitectureDecisionError(ValueError):
    """Raised when deterministic architecture decision input is invalid."""


class ArchitectureHumanGate(ArchitectureDecisionError):
    """Raised when an architecture action requires human authority."""


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArchitectureDecisionError(f"{name} must be an object")
    return value


def require_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ArchitectureDecisionError(f"{name} must be a lowercase SHA-256 digest")
    return value
