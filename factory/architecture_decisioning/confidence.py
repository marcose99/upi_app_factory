"""Deterministic architecture-review confidence calculation."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .canonical import canonical_sha256
from .review_models import ArchitectureReviewError
from .review_validation import require_contract_integrity


def calculate_architecture_confidence(
    packet: dict[str, Any], review_set: dict[str, Any], selected_candidate_id: str,
    review_contract: dict[str, Any], *, score_margin: float | None = None,
) -> dict[str, Any]:
    require_contract_integrity(review_contract, "review contract")
    reports = review_set.get("reports", [])
    if (review_set.get("architecture_packet_digest") != packet.get("packet_digest")
            or review_set.get("review_contract_digest") != review_contract.get("contract_digest")
            or len(reports) != len(review_contract["required_lanes"])):
        raise ArchitectureReviewError("confidence inputs are not bound to a complete review set")
    candidate_ids = {row["pattern_id"] for row in packet.get("scores", [])}
    if selected_candidate_id not in candidate_ids:
        raise ArchitectureReviewError("confidence candidate is not in the packet")
    recommendations = Counter(report["recommended_candidate_id"] for report in reports)
    agreement = recommendations[selected_candidate_id] / len(reports)
    evidence_values: list[float] = []
    for report in reports:
        refs = [ref for finding in report["findings"] for ref in finding["evidence_refs"]]
        finding_quality = 1.0 if not report["findings"] or refs else 0.0
        evidence_values.append((float(report["confidence"]) + finding_quality) / 2.0)
    evidence_quality = sum(evidence_values) / len(evidence_values)
    if score_margin is None:
        scores = sorted((float(row["total_score"]) for row in packet["scores"]), reverse=True)
        score_margin = (
            scores[0] - scores[1]
            if len(scores) > 1
            else review_contract["confidence"]["score_margin_full_credit"]
        )
    full_margin = review_contract["confidence"]["score_margin_full_credit"]
    margin_component = min(1.0, max(0.0, score_margin) / full_margin)
    winner_stability = packet.get("winner_stability")
    stability = (
        {"STABLE": 1.0, "CONDITIONAL": 0.5}.get(winner_stability, 0.0)
        if isinstance(winner_stability, str)
        else 0.0
    )
    components = {
        "reviewer_agreement": round(agreement, 6),
        "score_margin": round(margin_component, 6),
        "evidence_quality": round(evidence_quality, 6),
        "sensitivity_stability": stability,
    }
    weights = review_contract["confidence"]["weights"]
    score = round(sum(components[name] * weights[name] for name in components) / 100.0, 6)
    if score >= review_contract["confidence"]["high_threshold"]:
        level = "HIGH"
    elif score >= review_contract["confidence"]["medium_threshold"]:
        level = "MEDIUM"
    else:
        level = "LOW"
    result = {
        "schema_version": "upi-app-factory.architecture-confidence.v1",
        "selected_candidate_id": selected_candidate_id,
        "components": components,
        "score": score,
        "level": level,
    }
    result["digest"] = canonical_sha256(result)
    return result
