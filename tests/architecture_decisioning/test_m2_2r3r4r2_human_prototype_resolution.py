from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from factory.architecture_decisioning import (
    ArchitectureHumanGate,
    adjudicate_architecture_reviews,
    build_architecture_review_packet,
    build_evolution_contract,
    build_review_requests,
    build_reviewed_architecture_package,
    canonical_sha256,
    compile_driver_ir,
    decide_architecture,
    freeze_review_set,
    freeze_reviewed_architecture,
    resolve_prototype_required_adjudication,
    verify_reviewed_architecture_package,
)
from tests.architecture_decisioning import (
    test_m2_1a_c3_realization_conformance as c3,
)


HEXAGONAL = "MODULAR_MONOLITH_HEXAGONAL"
WORKFLOW = "WORKFLOW_CENTRIC_MODULAR_MONOLITH"


def _near_tie_inputs() -> dict[str, Any]:
    architecture = c3.architecture_contract()
    review = c3.review_contract()
    realization = c3.realization_contract()
    requirements_sha256 = c3.requirements_hash()
    driver_ir = compile_driver_ir(
        requirements_sha256, c3.observations(), architecture
    )
    dimensions = architecture["score_dimensions"]
    overrides: dict[str, dict[str, int]] = {}
    for row in architecture["patterns"]:
        candidate = str(row["pattern_id"])
        value = 90 if candidate == HEXAGONAL else 89 if candidate == WORKFLOW else 35
        overrides[candidate] = {dimension: value for dimension in dimensions}
    decision = decide_architecture(
        requirements_sha256=requirements_sha256,
        observations=c3.observations(),
        contract=architecture,
        context=c3.local_context(),
        dimension_overrides=overrides,
    )
    assert decision["selected_candidate_id"] == HEXAGONAL
    evolution = build_evolution_contract(decision, driver_ir, architecture)
    sensitivity: dict[str, Any] = {
        "base_winner": HEXAGONAL,
        "base_scores": decision["scores"],
        "scenarios": [],
        "winner_stability": "CONDITIONAL",
    }
    sensitivity["digest"] = canonical_sha256(sensitivity)
    packet = build_architecture_review_packet(
        decision,
        sensitivity,
        architecture,
        review,
        driver_ir=driver_ir,
        evolution_contract=evolution,
        evidence_catalog=[
            {
                "evidence_id": "R4R2-HUMAN-RESOLUTION-001",
                "sha256": "e" * 64,
                "purpose": "near-tie prototype resolution proof",
            }
        ],
    )
    requests = build_review_requests(packet, review)
    recommendations = [HEXAGONAL, WORKFLOW, HEXAGONAL, WORKFLOW, HEXAGONAL, WORKFLOW]
    reports = [
        c3.make_report(request, recommendation)
        for request, recommendation in zip(requests, recommendations)
    ]
    review_set = freeze_review_set(
        reports, packet, review, architecture
    )
    pre = adjudicate_architecture_reviews(
        packet, review_set, review, architecture
    )
    assert pre["status"] == "PROTOTYPE_REQUIRED"
    assert pre["prototype_candidates"] == [HEXAGONAL, WORKFLOW]
    return {
        "upstream_decision": decision,
        "driver_ir": driver_ir,
        "architecture_contract": architecture,
        "review_contract": review,
        "architecture_packet": packet,
        "review_set": review_set,
        "pre": pre,
        "realization_contract": realization,
        "requirements_sha256": requirements_sha256,
    }


def _approval_binding(requirements_sha256: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-human-approval-binding.v1",
        "status": "APPROVED",
        "scenario_id": "UPI-TEST-R4R2",
        "requirements_sha256": requirements_sha256,
        "approved_selected_candidate_id": WORKFLOW,
        "approval_statement": "APPROVE_TEST_HUMAN_PROTOTYPE_RESOLUTION",
        "approval_record_sha256": "a" * 64,
        "selection_digest_sha256": "b" * 64,
        "scope": "ARCHITECTURE_SELECTION_ONLY_NO_TECHNICAL_GATE_WAIVER",
        "quality_gates_waived": [],
    }
    value["approval_binding_digest"] = canonical_sha256(value)
    return value


def _prototype_evidence(requirements_sha256: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-prototype-qualification-evidence.v1",
        "scenario_id": "UPI-TEST-R4R2",
        "requirements_sha256": requirements_sha256,
        "selected_candidate_id": WORKFLOW,
        "mandatory_pass": True,
        "checks": {
            "generation_success": True,
            "deterministic_regeneration": True,
            "compileall_pass": True,
            "pytest_pass": True,
            "workflow_transition_executable": True,
        },
        "failure_codes": [],
        "prototype_package_sha256": "c" * 64,
        "prototype_contract_sha256": "d" * 64,
    }
    value["prototype_evidence_digest"] = canonical_sha256(value)
    return value


def _resolved_package() -> dict[str, Any]:
    inputs = _near_tie_inputs()
    final = resolve_prototype_required_adjudication(
        pre_resolution_adjudication=inputs["pre"],
        packet=inputs["architecture_packet"],
        review_set=inputs["review_set"],
        review_contract=inputs["review_contract"],
        selected_candidate_id=WORKFLOW,
        requirements_sha256=inputs["requirements_sha256"],
        approval_binding=_approval_binding(inputs["requirements_sha256"]),
        prototype_evidence=_prototype_evidence(inputs["requirements_sha256"]),
    )
    return build_reviewed_architecture_package(
        upstream_decision=inputs["upstream_decision"],
        driver_ir=inputs["driver_ir"],
        architecture_contract=inputs["architecture_contract"],
        review_contract=inputs["review_contract"],
        architecture_packet=inputs["architecture_packet"],
        review_set=inputs["review_set"],
        adjudication=final,
        realization_contract=inputs["realization_contract"],
    )


def test_human_resolution_preserves_machine_confidence_and_freezes_selected_prototype() -> None:
    package = _resolved_package()
    adjudication = package["adjudication"]
    confidence = adjudication["confidence"]
    resolution = adjudication["human_resolution"]
    freeze = package["reviewed_freeze"]

    assert adjudication["selected_candidate_id"] == WORKFLOW
    assert confidence["selected_candidate_id"] == WORKFLOW
    assert confidence["level"] == "LOW"
    assert resolution["automated_confidence_level"] == "LOW"
    assert resolution["confidence_inflated_by_human_approval"] is False
    assert resolution["quality_gates_waived"] == []
    assert freeze["selected_candidate_id"] == WORKFLOW
    assert freeze["governance_resolution_status"] == (
        "HUMAN_RESOLVED_AFTER_MANDATORY_PROTOTYPE_QUALIFICATION"
    )
    assert freeze["human_resolution_digest"] == resolution["human_resolution_digest"]
    assert package["reviewed_decision"]["human_resolution_digest"] == resolution[
        "human_resolution_digest"
    ]
    assert verify_reviewed_architecture_package(package)


def test_prototype_required_adjudication_cannot_be_relabelled_without_human_evidence() -> None:
    inputs = _near_tie_inputs()
    forged = deepcopy(inputs["pre"])
    forged.update(
        {
            "status": "SELECTED_REVIEWED",
            "selected_candidate_id": WORKFLOW,
            "prototype_candidates": [],
        }
    )
    forged.pop("adjudication_digest", None)
    forged["adjudication_digest"] = canonical_sha256(forged)
    with pytest.raises(ArchitectureHumanGate):
        freeze_reviewed_architecture(
            upstream_decision=inputs["upstream_decision"],
            driver_ir=inputs["driver_ir"],
            architecture_contract=inputs["architecture_contract"],
            review_contract=inputs["review_contract"],
            architecture_packet=inputs["architecture_packet"],
            review_set=inputs["review_set"],
            adjudication=forged,
            realization_contract=inputs["realization_contract"],
        )


@pytest.mark.parametrize(
    "mutation",
    ("approval_candidate", "prototype_gate", "confidence_inflation", "cross_scenario"),
)
def test_human_resolution_tampering_fails_package_verification(mutation: str) -> None:
    package = _resolved_package()
    bad = deepcopy(package)
    if mutation == "approval_candidate":
        bad["adjudication"]["human_resolution"]["approval_binding"][
            "approved_selected_candidate_id"
        ] = HEXAGONAL
    elif mutation == "prototype_gate":
        bad["adjudication"]["human_resolution"]["prototype_evidence"]["checks"][
            "pytest_pass"
        ] = False
    elif mutation == "confidence_inflation":
        bad["adjudication"]["confidence"]["level"] = "HIGH"
        bad["adjudication"]["confidence"]["score"] = 1.0
        bad["adjudication"]["confidence"]["digest"] = canonical_sha256(
            {
                key: value
                for key, value in bad["adjudication"]["confidence"].items()
                if key != "digest"
            }
        )
    else:
        bad["adjudication"]["human_resolution"]["prototype_evidence"][
            "scenario_id"
        ] = "UPI-OTHER-SCENARIO"
    bad["adjudication"].pop("adjudication_digest", None)
    bad["adjudication"]["adjudication_digest"] = canonical_sha256(
        bad["adjudication"]
    )
    bad.pop("package_digest", None)
    bad["package_digest"] = canonical_sha256(bad)
    assert verify_reviewed_architecture_package(bad) is False
