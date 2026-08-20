"""Deterministic veto-aware architecture review adjudication."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from typing import Any

from .canonical import canonical_sha256
from .confidence import calculate_architecture_confidence
from .review_models import ArchitectureReviewError, ArchitectureReviewIncomplete
from .review_validation import require_contract_integrity


def _validate_bindings(
    packet: dict[str, Any], review_set: dict[str, Any],
    rc: dict[str, Any], ac: dict[str, Any],
) -> None:
    expected_digest = canonical_sha256(
        {key: value for key, value in review_set.items() if key != "review_set_digest"}
    )
    if review_set.get("review_set_digest") != expected_digest:
        raise ArchitectureReviewError("review set digest is invalid")
    if review_set.get("architecture_packet_digest") != packet.get("packet_digest"):
        raise ArchitectureReviewError("review set is bound to another packet")
    if (
        review_set.get("review_contract_digest") != rc.get("contract_digest")
        or packet.get("review_contract_digest") != rc.get("contract_digest")
    ):
        raise ArchitectureReviewError("review contract binding is invalid")
    if (
        review_set.get("architecture_contract_digest") != ac.get("contract_digest")
        or packet.get("architecture_contract_digest") != ac.get("contract_digest")
    ):
        raise ArchitectureReviewError("architecture contract binding is invalid")
    if (
        review_set.get("lane_ids") != rc["required_lanes"]
        or len(review_set.get("reports", [])) != len(rc["required_lanes"])
    ):
        raise ArchitectureReviewIncomplete("all frozen review lanes are required")


def adjudicate_architecture_reviews(
    packet: dict[str, Any], review_set: dict[str, Any],
    review_contract: dict[str, Any], architecture_contract: dict[str, Any],
) -> dict[str, Any]:
    require_contract_integrity(review_contract, "review contract")
    require_contract_integrity(architecture_contract, "architecture contract")
    _validate_bindings(packet, review_set, review_contract, architecture_contract)
    dimensions = architecture_contract["score_dimensions"]
    weights = architecture_contract["default_weights"]
    adjustments: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    vetoed: set[str] = set()
    veto_findings: list[dict[str, Any]] = []
    for report in review_set["reports"]:
        for assessment in report["candidate_assessments"]:
            for dimension, adjustment in assessment["score_adjustments"].items():
                adjustments[assessment["candidate_id"]][dimension].append(float(adjustment))
        for finding in report["findings"]:
            if finding["disposition"] == "VETO":
                vetoed.add(finding["candidate_id"])
                veto_findings.append(deepcopy(finding))
    revised = []
    for row in packet["scores"]:
        candidate = row["pattern_id"]
        scores: dict[str, float] = {}
        for dimension in dimensions:
            values = adjustments[candidate][dimension]
            mean = sum(values) / len(values) if values else 0.0
            scores[dimension] = float(row["dimension_scores"][dimension]) + mean
        numerator = sum(
            Decimal(str(scores[dimension])) * Decimal(weights[dimension])
            for dimension in dimensions
        )
        total = numerator / Decimal(100)
        revised.append({
            "pattern_id": candidate,
            "total_score": float(total),
            "dimension_scores": scores,
        })
    revised.sort(key=lambda row: (-row["total_score"], row["pattern_id"]))
    upstream = packet["upstream_decision_status"]
    selected: str | None = None
    status: str
    prototype_candidates: list[str] = []
    preserved = upstream in review_contract["upstream_non_bypassable_statuses"]
    confidence: dict[str, Any] | None = None
    if preserved:
        status = upstream
        selected = packet["upstream_selected_candidate_id"]
    else:
        constraints = packet.get("constraints", {})
        eligible = [
            row for row in revised
            if constraints.get(row["pattern_id"], {}).get("outcome") == "ALLOW"
            and row["pattern_id"] not in vetoed
        ]
        if not eligible:
            status = "HUMAN_GATE"
        else:
            selected = eligible[0]["pattern_id"]
            margin = (
                eligible[0]["total_score"] - eligible[1]["total_score"]
                if len(eligible) > 1
                else review_contract["confidence"]["score_margin_full_credit"]
            )
            confidence = calculate_architecture_confidence(
                packet, review_set, selected, review_contract, score_margin=margin
            )
            upstream_scores = sorted(
                (float(row["total_score"]) for row in packet["scores"]),
                reverse=True,
            )
            upstream_margin = (
                upstream_scores[0] - upstream_scores[1]
                if len(upstream_scores) > 1
                else review_contract["confidence"]["score_margin_full_credit"]
            )
            near_tie_basis = review_contract.get(
                "near_tie_basis", "UPSTREAM_SCORE_MARGIN"
            )
            near_tie_margin = (
                margin
                if near_tie_basis == "REVISED_ELIGIBLE_MARGIN"
                else upstream_margin
            )
            if (
                len(eligible) > 1
                and near_tie_margin < review_contract["near_tie_margin"]
                and confidence["level"] != "HIGH"
            ):
                status = "PROTOTYPE_REQUIRED"
                prototype_candidates = [eligible[0]["pattern_id"], eligible[1]["pattern_id"]]
                selected = None
            else:
                status = "SELECTED_REVIEWED"
    result = {
        "schema_version": review_contract["adjudication_schema_version"],
        "architecture_packet_digest": packet["packet_digest"],
        "review_set_digest": review_set["review_set_digest"],
        "review_contract_digest": review_contract["contract_digest"],
        "architecture_contract_digest": architecture_contract["contract_digest"],
        "status": status,
        "selected_candidate_id": selected,
        "upstream_status_preserved": preserved,
        "vetoed_candidates": sorted(vetoed),
        "veto_findings": sorted(
            veto_findings,
            key=lambda item: (item["candidate_id"], item["finding_id"]),
        ),
        "revised_scores": revised,
        "selection_changed_by_review": (
            status == "SELECTED_REVIEWED"
            and selected != packet["upstream_selected_candidate_id"]
        ),
        "prototype_candidates": prototype_candidates,
        "confidence": confidence,
    }
    result["adjudication_digest"] = canonical_sha256(result)
    return result
