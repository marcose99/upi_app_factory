"""Canonical JSON and digest primitives."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .models import ArchitectureDecisionError


def canonical_json(value: Any) -> str:
    """Serialize JSON data with stable ordering and no insignificant whitespace."""
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ArchitectureDecisionError(f"value is not canonical JSON data: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArchitectureDecisionError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ArchitectureDecisionError(f"{name} must be a finite number")
    return result
