"""Deterministic weight-scenario sensitivity analysis."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .canonical import canonical_sha256
from .models import ArchitectureDecisionError
from .scoring import score_candidates


def run_sensitivity_analysis(
    candidates: Sequence[Mapping[str, Any]],
    base_weights: Mapping[str, Any],
    scenarios: Sequence[Mapping[str, Any]],
    dimension_overrides: Optional[Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    base_scores = score_candidates(candidates, base_weights, dimension_overrides)
    if not base_scores:
        raise ArchitectureDecisionError("sensitivity analysis requires candidates")
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in seen:
            raise ArchitectureDecisionError("scenario IDs must be unique non-empty strings")
        seen.add(scenario_id)
        scores = score_candidates(candidates, scenario.get("weights", {}), dimension_overrides)
        rows.append(
            {"scenario_id": scenario_id, "winner": scores[0]["pattern_id"], "scores": scores}
        )
    base_winner = base_scores[0]["pattern_id"]
    result: dict[str, Any] = {
        "base_winner": base_winner,
        "base_scores": base_scores,
        "scenarios": rows,
        "winner_stability": (
            "STABLE" if all(row["winner"] == base_winner for row in rows) else "CONDITIONAL"
        ),
    }
    result["digest"] = canonical_sha256(result)
    return result
