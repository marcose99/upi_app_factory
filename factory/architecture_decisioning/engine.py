"""Architecture decision orchestration without generation integration."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from .canonical import canonical_sha256
from .constraints import evaluate_constraints
from .driver_compiler import compile_driver_ir
from .registry import generate_candidates
from .risk import classify_authority
from .scoring import score_candidates


def decide_architecture(
    requirements_sha256: str,
    observations: Iterable[Mapping[str, Any]],
    contract: Mapping[str, Any],
    context: Mapping[str, Any],
    weights: Optional[Mapping[str, Any]] = None,
    dimension_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    driver_ir = compile_driver_ir(requirements_sha256, observations, contract)
    candidates = generate_candidates(driver_ir, contract)
    constraint_rows = {
        candidate["pattern_id"]: evaluate_constraints(candidate, contract, context)
        for candidate in candidates
    }
    scores = score_candidates(
        candidates,
        weights or contract.get("default_weights", {}),
        dimension_overrides,
    )
    admissible_scores = [
        row for row in scores
        if constraint_rows[row["pattern_id"]]["outcome"] != "REJECT"
    ]
    by_id = {candidate["pattern_id"]: candidate for candidate in candidates}
    if not admissible_scores:
        selected_id = None
        selected_state = None
        status = "NO_ADMISSIBLE"
        authority = "A4"
    else:
        winner = admissible_scores[0]
        selected_id = winner["pattern_id"]
        selected = by_id[selected_id]
        selected_state = selected["execution_state"]
        outcome = constraint_rows[selected_id]["outcome"]
        authority = classify_authority(selected, constraint_rows[selected_id], context, contract)
        if outcome == "HUMAN_GATE":
            status = "HUMAN_GATE"
        elif outcome == "ANALYSIS_ONLY":
            status = "FACTORY_CAPABILITY_GAP"
        else:
            status = "SELECTED"
    result: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-decision.v1",
        "requirements_sha256": requirements_sha256,
        "driver_ir_digest": driver_ir["digest"],
        "contract_digest": contract.get("contract_digest"),
        "selected_candidate_id": selected_id,
        "selected_execution_state": selected_state,
        "decision_status": status,
        "authority_class": authority,
        "scores": scores,
        "constraints": constraint_rows,
    }
    result["decision_digest"] = canonical_sha256(result)
    return result
