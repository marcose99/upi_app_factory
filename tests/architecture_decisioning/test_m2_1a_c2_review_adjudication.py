from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import threading
from typing import Any

import pytest

from factory.architecture_decisioning import (
    ArchitectureReviewError,
    ArchitectureReviewIncomplete,
    ArchitectureReviewSupervisor,
    adjudicate_architecture_reviews,
    build_architecture_review_packet,
    build_review_requests,
    calculate_architecture_confidence,
    canonical_sha256,
    freeze_review_set,
    load_architecture_contract,
    load_architecture_review_contract,
    validate_review_report,
)

ROOT = Path(__file__).resolve().parents[2]
ARCH_CONTRACT = ROOT / "config/architecture_decisioning/kernel_contract.v2.json"
REVIEW_CONTRACT = ROOT / "config/architecture_decisioning/review_contract.v1.json"

REQ_SHA = "a" * 64
CANDIDATES = (
    "MODULAR_MONOLITH_HEXAGONAL",
    "WORKFLOW_CENTRIC_MODULAR_MONOLITH",
    "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX",
    "CQRS_EVENT_ORIENTED",
    "SERVICE_ORIENTED_DISTRIBUTED",
)

def arch_contract() -> dict[str, Any]:
    return load_architecture_contract(ARCH_CONTRACT)

def review_contract() -> dict[str, Any]:
    return load_architecture_review_contract(REVIEW_CONTRACT)

def base_decision(status: str = "SELECTED") -> dict[str, Any]:
    ac = arch_contract()
    rows = []
    totals = [90.0, 86.0, 84.0, 80.0, 70.0]
    constraints = {}
    for cid, total in zip(CANDIDATES, totals):
        dims = {dimension: total for dimension in ac["score_dimensions"]}
        rows.append({"pattern_id": cid, "total_score": total, "dimension_scores": dims})
        if cid == "CQRS_EVENT_ORIENTED":
            constraints[cid] = {"outcome": "ANALYSIS_ONLY", "reasons": ["analysis only"]}
        elif cid == "SERVICE_ORIENTED_DISTRIBUTED":
            constraints[cid] = {"outcome": "HUMAN_GATE", "reasons": ["external infrastructure"]}
        else:
            constraints[cid] = {"outcome": "ALLOW", "reasons": []}
    selected = CANDIDATES[0]
    execution = "EXECUTABLE"
    authority = "A3"
    if status == "HUMAN_GATE":
        selected = "SERVICE_ORIENTED_DISTRIBUTED"
        execution = "HUMAN_ENABLEMENT_REQUIRED"
        authority = "A4"
    elif status == "FACTORY_CAPABILITY_GAP":
        selected = "CQRS_EVENT_ORIENTED"
        execution = "ANALYSIS_ONLY"
        authority = "A4"
    result = {
        "schema_version": "upi-app-factory.architecture-decision.v1",
        "requirements_sha256": REQ_SHA,
        "driver_ir_digest": "b" * 64,
        "contract_digest": ac["contract_digest"],
        "selected_candidate_id": selected,
        "selected_execution_state": execution,
        "decision_status": status,
        "authority_class": authority,
        "scores": rows,
        "constraints": constraints,
    }
    result["decision_digest"] = canonical_sha256(result)
    return result

def sensitivity(stability: str = "STABLE") -> dict[str, Any]:
    result = {
        "base_winner": CANDIDATES[0],
        "base_scores": base_decision()["scores"],
        "scenarios": [],
        "winner_stability": stability,
    }
    result["digest"] = canonical_sha256(result)
    return result

def packet(status: str = "SELECTED", stability: str = "STABLE") -> dict[str, Any]:
    return build_architecture_review_packet(
        decision=base_decision(status),
        sensitivity=sensitivity(stability),
        architecture_contract=arch_contract(),
        review_contract=review_contract(),
    )

def make_report(
    request: dict[str, Any],
    *,
    recommendation: str = CANDIDATES[0],
    finding: dict[str, Any] | None = None,
    adjustments: dict[str, dict[str, float]] | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    assessments = []
    for cid in CANDIDATES:
        assessments.append({
            "candidate_id": cid,
            "score_adjustments": dict((adjustments or {}).get(cid, {})),
            "summary": f"independent assessment of {cid}",
        })
    report = {
        "schema_version": review_contract()["report_schema_version"],
        "lane_id": request["lane_id"],
        "request_digest": request["request_digest"],
        "architecture_packet_digest": request["architecture_packet_digest"],
        "prior_reports_visible": False,
        "recommended_candidate_id": recommendation,
        "candidate_assessments": assessments,
        "findings": [] if finding is None else [finding],
        "confidence": confidence,
    }
    report["report_digest"] = canonical_sha256(report)
    return report

def complete_reports(p: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    requests = build_review_requests(p, review_contract())
    return [make_report(req, **kwargs) for req in requests]

def security_veto(candidate: str = CANDIDATES[0]) -> dict[str, Any]:
    return {
        "finding_id": "SEC-001",
        "candidate_id": candidate,
        "category": "SECURITY_TRUST_BOUNDARY",
        "severity": "HIGH",
        "disposition": "VETO",
        "claim": "candidate creates a material unmitigated trust-boundary risk",
        "evidence_refs": ["ARCH-SEC-EVIDENCE-001"],
    }

def test_contract_has_exact_six_blind_lanes_and_bounded_parallelism() -> None:
    c = review_contract()
    assert c["execution_mode"] == "PARALLEL_BLIND"
    assert len(c["required_lanes"]) == 6
    assert len(set(c["required_lanes"])) == 6
    assert c["max_parallelism"] == 6
    assert c["blind_first_pass_required"] is True
    assert c["all_lanes_required_before_adjudication"] is True

def test_review_packet_is_digest_bound_and_contains_no_provider_or_prior_report_state() -> None:
    p = packet()
    assert p["decision_digest"] == base_decision()["decision_digest"]
    assert p["sensitivity_digest"] == sensitivity()["digest"]
    assert p["architecture_contract_digest"] == arch_contract()["contract_digest"]
    assert "provider" not in p
    assert "prior_reports" not in p
    assert p["packet_digest"] == canonical_sha256({k: v for k, v in p.items() if k != "packet_digest"})

def test_review_requests_are_blind_distinct_and_ordered_by_frozen_lane_order() -> None:
    p = packet()
    requests = build_review_requests(p, review_contract())
    assert [r["lane_id"] for r in requests] == review_contract()["required_lanes"]
    assert len({r["request_digest"] for r in requests}) == 6
    for r in requests:
        assert r["prior_reports_visible"] is False
        assert "prior_reports" not in r
        assert r["architecture_packet_digest"] == p["packet_digest"]

def test_report_validation_rejects_prior_report_visibility_unknown_candidate_and_bad_adjustment() -> None:
    p = packet()
    req = build_review_requests(p, review_contract())[0]
    good = make_report(req)
    assert validate_review_report(good, req, p, review_contract(), arch_contract())["report_digest"] == good["report_digest"]

    bad = deepcopy(good)
    bad["prior_reports_visible"] = True
    bad["report_digest"] = canonical_sha256({k: v for k, v in bad.items() if k != "report_digest"})
    with pytest.raises(ArchitectureReviewError):
        validate_review_report(bad, req, p, review_contract(), arch_contract())

    bad = deepcopy(good)
    bad["recommended_candidate_id"] = "INVENTED"
    bad["report_digest"] = canonical_sha256({k: v for k, v in bad.items() if k != "report_digest"})
    with pytest.raises(ArchitectureReviewError):
        validate_review_report(bad, req, p, review_contract(), arch_contract())

    bad = deepcopy(good)
    bad["candidate_assessments"][0]["score_adjustments"] = {"security": 6}
    bad["report_digest"] = canonical_sha256({k: v for k, v in bad.items() if k != "report_digest"})
    with pytest.raises(ArchitectureReviewError):
        validate_review_report(bad, req, p, review_contract(), arch_contract())

def test_veto_requires_protected_category_high_or_critical_and_evidence() -> None:
    p = packet()
    req = build_review_requests(p, review_contract())[0]
    good = make_report(req, finding=security_veto())
    validate_review_report(good, req, p, review_contract(), arch_contract())
    mutations: tuple[dict[str, Any], ...] = (
        {"category": "OPERABILITY"},
        {"severity": "MEDIUM"},
        {"evidence_refs": []},
    )
    for mutation in mutations:
        bad = make_report(req, finding={**security_veto(), **mutation})
        with pytest.raises(ArchitectureReviewError):
            validate_review_report(bad, req, p, review_contract(), arch_contract())

def test_review_set_requires_exactly_one_report_per_required_lane_and_is_order_independent() -> None:
    p = packet()
    reports = complete_reports(p)
    frozen1 = freeze_review_set(reports, p, review_contract(), arch_contract())
    frozen2 = freeze_review_set(list(reversed(reports)), p, review_contract(), arch_contract())
    assert frozen1 == frozen2
    assert frozen1["review_set_digest"] == canonical_sha256({k: v for k, v in frozen1.items() if k != "review_set_digest"})
    with pytest.raises(ArchitectureReviewIncomplete):
        freeze_review_set(reports[:-1], p, review_contract(), arch_contract())
    with pytest.raises(ArchitectureReviewIncomplete):
        freeze_review_set(reports + [reports[0]], p, review_contract(), arch_contract())

def test_supervisor_proves_actual_concurrent_blind_fanout() -> None:
    p = packet()
    c = review_contract()
    barrier = threading.Barrier(len(c["required_lanes"]), timeout=4)
    seen: list[tuple[str, bool]] = []
    lock = threading.Lock()
    def provider(request: dict[str, Any]) -> dict[str, Any]:
        with lock:
            seen.append((request["lane_id"], "prior_reports" in request))
        barrier.wait()
        return make_report(request)
    providers = {lane: provider for lane in reversed(c["required_lanes"])}
    supervisor = ArchitectureReviewSupervisor(c, arch_contract())
    review_set = supervisor.run_blind_reviews(p, providers)
    assert review_set["execution_mode"] == "PARALLEL_BLIND"
    assert review_set["lane_ids"] == c["required_lanes"]
    assert len(seen) == 6
    assert all(prior_visible is False for _, prior_visible in seen)

def test_supervisor_fails_closed_when_provider_missing_or_errors() -> None:
    p = packet()
    c = review_contract()
    supervisor = ArchitectureReviewSupervisor(c, arch_contract())
    providers = {lane: (lambda request: make_report(request)) for lane in c["required_lanes"][:-1]}
    with pytest.raises(ArchitectureReviewIncomplete):
        supervisor.run_blind_reviews(p, providers)
    def boom(_request: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("provider failure")
    providers = {lane: (boom if lane == "SECURITY_CHALLENGER" else (lambda request: make_report(request))) for lane in c["required_lanes"]}
    with pytest.raises(ArchitectureReviewIncomplete):
        supervisor.run_blind_reviews(p, providers)

def test_protected_high_veto_cannot_be_averaged_away_and_changes_selection() -> None:
    p = packet()
    requests = build_review_requests(p, review_contract())
    reports = [make_report(req, finding=security_veto() if req["lane_id"] == "SECURITY_CHALLENGER" else None) for req in requests]
    review_set = freeze_review_set(reports, p, review_contract(), arch_contract())
    result = adjudicate_architecture_reviews(p, review_set, review_contract(), arch_contract())
    assert CANDIDATES[0] in result["vetoed_candidates"]
    assert result["selected_candidate_id"] == CANDIDATES[1]
    assert result["selection_changed_by_review"] is True
    assert result["status"] == "SELECTED_REVIEWED"

def test_review_cannot_bypass_upstream_human_gate_or_capability_gap() -> None:
    for upstream in ("HUMAN_GATE", "FACTORY_CAPABILITY_GAP"):
        p = packet(status=upstream)
        rs = freeze_review_set(complete_reports(p), p, review_contract(), arch_contract())
        result = adjudicate_architecture_reviews(p, rs, review_contract(), arch_contract())
        assert result["status"] == upstream
        assert result["selected_candidate_id"] == base_decision(upstream)["selected_candidate_id"]
        assert result["upstream_status_preserved"] is True

def test_all_automatic_candidates_vetoed_requires_human_gate() -> None:
    p = packet()
    reqs = build_review_requests(p, review_contract())
    reports = []
    for idx, req in enumerate(reqs):
        target = CANDIDATES[idx % 3]
        finding = {
            "finding_id": f"PAY-{idx}",
            "candidate_id": target,
            "category": "PAYMENT_INTEGRITY",
            "severity": "HIGH",
            "disposition": "VETO",
            "claim": "material money-safety risk",
            "evidence_refs": [f"PAY-EVIDENCE-{idx}"],
        }
        reports.append(make_report(req, finding=finding))
    rs = freeze_review_set(reports, p, review_contract(), arch_contract())
    result = adjudicate_architecture_reviews(p, rs, review_contract(), arch_contract())
    assert set(CANDIDATES[:3]) <= set(result["vetoed_candidates"])
    assert result["status"] == "HUMAN_GATE"
    assert result["selected_candidate_id"] is None

def test_score_adjustment_aggregation_is_bounded_mean_and_deterministic() -> None:
    p = packet()
    reqs = build_review_requests(p, review_contract())
    reports = [make_report(req, adjustments={CANDIDATES[1]: {"evolvability": 5}}) for req in reqs]
    rs = freeze_review_set(reports, p, review_contract(), arch_contract())
    r1 = adjudicate_architecture_reviews(p, rs, review_contract(), arch_contract())
    r2 = adjudicate_architecture_reviews(p, rs, review_contract(), arch_contract())
    assert r1 == r2
    row = next(row for row in r1["revised_scores"] if row["pattern_id"] == CANDIDATES[1])
    base = next(row for row in p["scores"] if row["pattern_id"] == CANDIDATES[1])
    assert row["dimension_scores"]["evolvability"] == base["dimension_scores"]["evolvability"] + 5

def test_confidence_is_deterministic_and_conditional_sensitivity_reduces_it() -> None:
    stable_p = packet(stability="STABLE")
    stable_rs = freeze_review_set(complete_reports(stable_p), stable_p, review_contract(), arch_contract())
    stable = calculate_architecture_confidence(stable_p, stable_rs, CANDIDATES[0], review_contract())
    conditional_p = packet(stability="CONDITIONAL")
    conditional_rs = freeze_review_set(complete_reports(conditional_p), conditional_p, review_contract(), arch_contract())
    conditional = calculate_architecture_confidence(conditional_p, conditional_rs, CANDIDATES[0], review_contract())
    assert stable["score"] > conditional["score"]
    assert stable["digest"] == canonical_sha256({k: v for k, v in stable.items() if k != "digest"})

def test_near_tie_with_non_high_confidence_requires_prototype_not_silent_selection() -> None:
    p = deepcopy(packet(stability="CONDITIONAL"))
    p["scores"][0]["total_score"] = 90.0
    p["scores"][1]["total_score"] = 89.0
    p["packet_digest"] = canonical_sha256({k: v for k, v in p.items() if k != "packet_digest"})
    reqs = build_review_requests(p, review_contract())
    recs = [CANDIDATES[0], CANDIDATES[1], CANDIDATES[0], CANDIDATES[1], CANDIDATES[0], CANDIDATES[1]]
    reports = [make_report(req, recommendation=rec) for req, rec in zip(reqs, recs)]
    rs = freeze_review_set(reports, p, review_contract(), arch_contract())
    result = adjudicate_architecture_reviews(p, rs, review_contract(), arch_contract())
    assert result["status"] == "PROTOTYPE_REQUIRED"
    assert result["prototype_candidates"] == [CANDIDATES[0], CANDIDATES[1]]

def test_adjudication_is_bound_to_packet_review_set_and_contracts() -> None:
    p = packet()
    rs = freeze_review_set(complete_reports(p), p, review_contract(), arch_contract())
    result = adjudicate_architecture_reviews(p, rs, review_contract(), arch_contract())
    assert result["architecture_packet_digest"] == p["packet_digest"]
    assert result["review_set_digest"] == rs["review_set_digest"]
    assert result["review_contract_digest"] == review_contract()["contract_digest"]
    assert result["architecture_contract_digest"] == arch_contract()["contract_digest"]
    assert result["adjudication_digest"] == canonical_sha256({k: v for k, v in result.items() if k != "adjudication_digest"})
