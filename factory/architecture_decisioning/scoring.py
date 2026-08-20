"""Exact deterministic weighted scoring."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Optional, Sequence

from .canonical import require_finite_number
from .models import ArchitectureDecisionError


def score_candidates(
    candidates: Sequence[Mapping[str, Any]],
    weights: Mapping[str, Any],
    dimension_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> list[dict[str, Any]]:
    if not isinstance(weights, Mapping) or not weights:
        raise ArchitectureDecisionError("weights must be a non-empty object")
    normalized_weights: dict[str, int] = {}
    for dimension, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ArchitectureDecisionError("weights must be non-negative integers")
        normalized_weights[dimension] = value
    if sum(normalized_weights.values()) != 100:
        raise ArchitectureDecisionError("weights must sum to exactly 100")
    overrides = dimension_overrides or {}
    known_ids = {str(candidate.get("pattern_id")) for candidate in candidates}
    if not set(overrides).issubset(known_ids):
        raise ArchitectureDecisionError("dimension override names an unknown candidate")
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        pattern_id = str(candidate.get("pattern_id"))
        base = candidate.get("base_scores")
        if not isinstance(base, Mapping) or set(base) != set(normalized_weights):
            raise ArchitectureDecisionError(f"scores for {pattern_id} do not match weights")
        candidate_overrides = overrides.get(pattern_id, {})
        if not set(candidate_overrides).issubset(normalized_weights):
            raise ArchitectureDecisionError(f"unknown score dimension override for {pattern_id}")
        dimensions: dict[str, float] = {}
        numerator = Decimal(0)
        for dimension, weight in normalized_weights.items():
            raw = candidate_overrides.get(dimension, base[dimension])
            score = require_finite_number(raw, f"{pattern_id}.{dimension}")
            if not 0 <= score <= 100:
                raise ArchitectureDecisionError("dimension scores must be between 0 and 100")
            dimensions[dimension] = score
            numerator += Decimal(str(score)) * Decimal(weight)
        total = numerator / Decimal(100)
        scored.append({
            "pattern_id": pattern_id,
            "total_score": float(total),
            "dimension_scores": dimensions,
        })
    return sorted(scored, key=lambda row: (-row["total_score"], row["pattern_id"]))
