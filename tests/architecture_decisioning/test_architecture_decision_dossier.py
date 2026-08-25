from __future__ import annotations

from copy import deepcopy
from typing import Any

from factory.architecture_decisioning import (
    BOUNDED_CLAIM_STATUS,
    SUFFICIENT_CLAIM_STATUS,
    build_architecture_decision_dossier,
    canonical_sha256,
    evaluate_nfr_sufficiency,
    render_architecture_decision_dossier_markdown,
    verify_architecture_decision_dossier,
)
from tests.architecture_decisioning import test_m2_1a_c3_realization_conformance as c3


WORKFLOW = "WORKFLOW_CENTRIC_MODULAR_MONOLITH"


def _conformance(package: dict[str, Any]) -> dict[str, Any]:
    freeze = package["reviewed_freeze"]
    report: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-conformance.v1",
        "status": "PASS",
        "selected_candidate_id": freeze["selected_candidate_id"],
        "adapter_id": freeze["adapter_id"],
        "architecture_freeze_digest": freeze["freeze_digest"],
        "realization_contract_digest": freeze["realization_contract_digest"],
        "rule_outcomes": {"required_generated_paths_present": True},
        "failed_rules": [],
        "source_identities": [],
    }
    report["conformance_digest"] = canonical_sha256(report)
    return report


def test_nfr_sufficiency_bounds_claim_when_architecture_changing_nfrs_are_unknown() -> None:
    package = c3.reviewed_package(WORKFLOW)
    gate = evaluate_nfr_sufficiency(package["driver_ir"])
    assert gate["gate_outcome"] == "PASS_BOUNDED_CLAIM_REQUIRED"
    assert gate["architecture_claim_status"] == BOUNDED_CLAIM_STATUS
    assert gate["global_optimum_claim_allowed"] is False
    assert "peak_tps" in gate["unknown_driver_ids"]
    assert "availability_slo" in gate["unknown_driver_ids"]


def test_nfr_sufficiency_allows_within_candidate_set_claim_when_required_nfrs_are_evidenced() -> None:
    drivers = []
    for driver_id in (
        "availability_slo",
        "peak_tps",
        "latency_slo_ms",
        "data_volume",
        "retention_days",
        "rpo_seconds",
        "rto_seconds",
        "deployment_independence",
    ):
        drivers.append(
            {
                "driver_id": driver_id,
                "source_class": "EXPLICIT_REQUIREMENT",
                "value": f"known-{driver_id}",
                "confidence": 1.0,
                "hard_constraint": False,
                "evidence": [f"E-{driver_id}"],
            }
        )
    gate = evaluate_nfr_sufficiency(
        {
            "schema_version": "upi-app-factory.architecture-driver-ir.v1",
            "requirements_sha256": "a" * 64,
            "drivers": drivers,
        }
    )
    assert gate["gate_outcome"] == "PASS_SUFFICIENT"
    assert gate["architecture_claim_status"] == SUFFICIENT_CLAIM_STATUS
    assert gate["unknown_driver_ids"] == []
    assert gate["missing_driver_ids"] == []
    assert gate["global_optimum_claim_allowed"] is False


def test_dossier_binds_candidates_reviews_conformance_tradeoffs_and_reconsideration() -> None:
    package = c3.reviewed_package(WORKFLOW)
    conformance = _conformance(package)
    dossier = build_architecture_decision_dossier(package, conformance)
    assert verify_architecture_decision_dossier(dossier, package, conformance)
    assert dossier["architecture_claim_status"] == BOUNDED_CLAIM_STATUS
    assert dossier["selected_candidate_id"] == WORKFLOW
    assert len(dossier["candidate_matrix"]) == len(package["architecture_packet"]["scores"])
    assert dossier["review_consensus"]["lane_count"] == 6
    assert dossier["review_consensus"]["selected_recommendation_count"] == 6
    assert dossier["architecture_conformance"]["status"] == "PASS"
    assert dossier["known_tradeoffs"]["lowest_revised_dimensions"]
    assert dossier["reconsideration_triggers"]
    assert dossier["global_optimum_claim_allowed"] is False

    markdown = render_architecture_decision_dossier_markdown(dossier)
    for heading in (
        "Requirements and architecture drivers",
        "NFR sufficiency gate",
        "Candidate decision matrix",
        "Sensitivity and review consensus",
        "Prototype / human decision",
        "Selected realization and conformance",
        "Known trade-offs",
        "Reconsideration triggers",
    ):
        assert heading in markdown
    assert BOUNDED_CLAIM_STATUS in markdown


def test_dossier_tampering_fails_reconstruction_verification() -> None:
    package = c3.reviewed_package(WORKFLOW)
    conformance = _conformance(package)
    dossier = build_architecture_decision_dossier(package, conformance)
    bad = deepcopy(dossier)
    bad["selected_candidate_id"] = "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX"
    assert verify_architecture_decision_dossier(bad, package, conformance) is False
