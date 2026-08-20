from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import time
from typing import Any

import pytest

from factory.architecture_decisioning import (
    ArchitectureReviewError,
    ArchitectureReviewIncomplete,
    ArchitectureReviewSupervisor,
    adjudicate_architecture_reviews,
    build_architecture_review_packet,
    build_review_requests,
    canonical_sha256,
    freeze_review_set,
    load_architecture_contract,
    load_architecture_review_contract,
)

ROOT = Path(__file__).resolve().parents[2]
ARCH_PATH = ROOT / "config/architecture_decisioning/kernel_contract.v2.json"
REVIEW_V2_PATH = ROOT / "config/architecture_decisioning/review_contract.v2.json"
CANDIDATES = (
    "MODULAR_MONOLITH_HEXAGONAL",
    "WORKFLOW_CENTRIC_MODULAR_MONOLITH",
    "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX",
    "CQRS_EVENT_ORIENTED",
    "SERVICE_ORIENTED_DISTRIBUTED",
)
REQ_SHA = "a" * 64


def arch_contract() -> dict[str, Any]:
    return load_architecture_contract(ARCH_PATH)


def review_contract() -> dict[str, Any]:
    return load_architecture_review_contract(REVIEW_V2_PATH)


def driver_ir() -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-driver-ir.v1",
        "requirements_sha256": REQ_SHA,
        "drivers": [
            {
                "driver_id": "peak_tps",
                "source_class": "UNKNOWN",
                "value": None,
                "confidence": 0.0,
                "hard_constraint": False,
                "evidence": [],
            }
        ],
    }
    value["digest"] = canonical_sha256(value)
    return value


def decision() -> dict[str, Any]:
    ac = arch_contract()
    totals = [90.0, 86.0, 84.0, 80.0, 70.0]
    rows = [
        {
            "pattern_id": candidate,
            "total_score": total,
            "dimension_scores": {
                dimension: total for dimension in ac["score_dimensions"]
            },
        }
        for candidate, total in zip(CANDIDATES, totals)
    ]
    constraints = {
        CANDIDATES[0]: {"outcome": "ALLOW", "reasons": []},
        CANDIDATES[1]: {"outcome": "ALLOW", "reasons": []},
        CANDIDATES[2]: {"outcome": "ALLOW", "reasons": []},
        CANDIDATES[3]: {"outcome": "ANALYSIS_ONLY", "reasons": []},
        CANDIDATES[4]: {"outcome": "HUMAN_GATE", "reasons": []},
    }
    value: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-decision.v1",
        "requirements_sha256": REQ_SHA,
        "driver_ir_digest": driver_ir()["digest"],
        "contract_digest": ac["contract_digest"],
        "selected_candidate_id": CANDIDATES[0],
        "selected_execution_state": "EXECUTABLE",
        "decision_status": "SELECTED",
        "authority_class": "A3",
        "scores": rows,
        "constraints": constraints,
    }
    value["decision_digest"] = canonical_sha256(value)
    return value


def sensitivity(stability: str = "CONDITIONAL") -> dict[str, Any]:
    value: dict[str, Any] = {
        "base_winner": CANDIDATES[0],
        "base_scores": decision()["scores"],
        "scenarios": [
            {
                "scenario_id": "ten_x_load",
                "winner": CANDIDATES[2],
                "scores": decision()["scores"],
            }
        ],
        "winner_stability": stability,
    }
    value["digest"] = canonical_sha256(value)
    return value


def evolution_contract() -> dict[str, Any]:
    d = decision()
    ac = arch_contract()
    value: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-evolution-contract.v1",
        "selected_candidate_id": d["selected_candidate_id"],
        "requirements_sha256": REQ_SHA,
        "driver_ir_digest": driver_ir()["digest"],
        "contract_digest": ac["contract_digest"],
        "decision_digest": d["decision_digest"],
        "compatibility_policy": "BACKWARD_COMPATIBLE_BY_DEFAULT",
        "migration_policy": "EXPAND_CONTRACT",
        "dependency_policy": "TRACK_EOL",
        "provider_model_policy": "PORTS_AND_ADAPTERS",
        "security_agility_policy": "CRYPTO_AGILITY",
        "reconsideration_triggers": ["measured load exceeds envelope"],
        "evidence_continuity_policy": "VERSIONED_LINEAGE",
        "durability_evaluation_digest": "d" * 64,
    }
    value["digest"] = canonical_sha256(value)
    return value


def packet(stability: str = "CONDITIONAL") -> dict[str, Any]:
    return build_architecture_review_packet(
        decision(),
        sensitivity(stability),
        arch_contract(),
        review_contract(),
        driver_ir=driver_ir(),
        evolution_contract=evolution_contract(),
        evidence_catalog=[
            {
                "evidence_id": "ARCH-EVIDENCE-001",
                "sha256": "e" * 64,
                "purpose": "architecture driver evidence",
            }
        ],
    )


def report(
    request: dict[str, Any],
    *,
    recommendation: str = CANDIDATES[0],
    adjustments: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": review_contract()["report_schema_version"],
        "lane_id": request["lane_id"],
        "request_digest": request["request_digest"],
        "architecture_packet_digest": request["architecture_packet_digest"],
        "prior_reports_visible": False,
        "recommended_candidate_id": recommendation,
        "candidate_assessments": [
            {
                "candidate_id": candidate,
                "score_adjustments": dict((adjustments or {}).get(candidate, {})),
                "summary": f"reviewed {candidate}",
            }
            for candidate in CANDIDATES
        ],
        "findings": [],
        "confidence": 0.9,
    }
    value["report_digest"] = canonical_sha256(value)
    return value


def report_set(
    p: dict[str, Any],
    *,
    recommendation: str = CANDIDATES[0],
    adjustments: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    requests = build_review_requests(p, review_contract())
    reports = [
        report(
            request,
            recommendation=recommendation,
            adjustments=adjustments,
        )
        for request in requests
    ]
    return freeze_review_set(
        reports, p, review_contract(), arch_contract()
    )


def test_v2_packet_contains_real_review_context_not_only_digests() -> None:
    p = packet()
    assert p["schema_version"] == "upi-app-factory.architecture-review-packet.v2"
    assert p["driver_ir"] == driver_ir()
    assert p["sensitivity"] == sensitivity()
    assert p["evolution_contract"] == evolution_contract()
    assert len(p["candidate_profiles"]) == len(CANDIDATES)
    assert [row["pattern_id"] for row in p["candidate_profiles"]] == list(CANDIDATES)
    assert p["evidence_catalog"][0]["evidence_id"] == "ARCH-EVIDENCE-001"


def test_v2_packet_refuses_missing_or_tampered_rich_context() -> None:
    with pytest.raises(ArchitectureReviewError):
        build_architecture_review_packet(
            decision(),
            sensitivity(),
            arch_contract(),
            review_contract(),
        )
    bad_driver = deepcopy(driver_ir())
    bad_driver["drivers"][0]["value"] = 10000
    with pytest.raises(ArchitectureReviewError):
        build_architecture_review_packet(
            decision(),
            sensitivity(),
            arch_contract(),
            review_contract(),
            driver_ir=bad_driver,
            evolution_contract=evolution_contract(),
        )


def test_contract_mutation_after_load_is_rejected_before_adjudication() -> None:
    p = packet(stability="STABLE")
    rs = report_set(p)
    bad_arch = deepcopy(arch_contract())
    bad_arch["default_weights"]["business_correctness"] = 100
    with pytest.raises(ArchitectureReviewError):
        adjudicate_architecture_reviews(p, rs, review_contract(), bad_arch)
    bad_review = deepcopy(review_contract())
    bad_review["near_tie_margin"] = 1000
    with pytest.raises(ArchitectureReviewError):
        adjudicate_architecture_reviews(p, rs, bad_review, arch_contract())


def test_reviewed_near_tie_uses_revised_eligible_margin() -> None:
    p = packet(stability="CONDITIONAL")
    all_dimensions = {
        dimension: 5.0 for dimension in arch_contract()["score_dimensions"]
    }
    rs = report_set(
        p,
        recommendation=CANDIDATES[1],
        adjustments={CANDIDATES[1]: all_dimensions},
    )
    result = adjudicate_architecture_reviews(
        p, rs, review_contract(), arch_contract()
    )
    assert result["revised_scores"][0]["pattern_id"] == CANDIDATES[1]
    assert result["revised_scores"][0]["total_score"] == 91.0
    assert result["revised_scores"][1]["total_score"] == 90.0
    assert result["confidence"]["level"] == "MEDIUM"
    assert result["status"] == "PROTOTYPE_REQUIRED"
    assert result["prototype_candidates"] == [CANDIDATES[1], CANDIDATES[0]]


def test_provider_timeout_fails_closed_without_waiting_for_full_provider_duration() -> None:
    c = deepcopy(review_contract())
    c.pop("contract_digest")
    c["provider_timeout_seconds"] = 0.05
    c["contract_digest"] = canonical_sha256(c)
    p = build_architecture_review_packet(
        decision(),
        sensitivity("STABLE"),
        arch_contract(),
        c,
        driver_ir=driver_ir(),
        evolution_contract=evolution_contract(),
        evidence_catalog=[],
    )
    requests = {
        request["lane_id"]: request
        for request in build_review_requests(p, c)
    }

    def slow_provider(request: dict[str, Any]) -> dict[str, Any]:
        time.sleep(0.25)
        return report(request)

    providers = {lane: slow_provider for lane in c["required_lanes"]}
    supervisor = ArchitectureReviewSupervisor(c, arch_contract())
    started = time.monotonic()
    with pytest.raises(ArchitectureReviewIncomplete, match="timed out"):
        supervisor.run_blind_reviews(p, providers)
    assert time.monotonic() - started < 0.20
    assert set(requests) == set(c["required_lanes"])


def test_v1_review_contract_remains_backward_compatible() -> None:
    v1 = load_architecture_review_contract(
        ROOT / "config/architecture_decisioning/review_contract.v1.json"
    )
    assert v1["schema_version"].endswith(".v1")
    assert "provider_timeout_seconds" not in v1
