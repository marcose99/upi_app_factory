"""Generate a bounded candidate set solely from the frozen registry."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .models import ArchitectureDecisionError


def generate_candidates(
    driver_ir: Mapping[str, Any], contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    if not isinstance(driver_ir.get("drivers"), list) or not driver_ir.get("digest"):
        raise ArchitectureDecisionError("invalid driver IR")
    patterns = contract.get("patterns")
    if not isinstance(patterns, list) or not 3 <= len(patterns) <= 5:
        raise ArchitectureDecisionError("frozen registry must contain between 3 and 5 patterns")
    result = [deepcopy(pattern) for pattern in patterns]
    result.sort(key=lambda row: str(row["pattern_id"]))
    return result
