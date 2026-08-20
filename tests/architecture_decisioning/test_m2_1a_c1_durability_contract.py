from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from factory.architecture_decisioning import (
    ArchitectureDecisionError,
    ArchitectureHumanGate,
    canonical_sha256,
    classify_authority,
    compile_driver_ir,
    decide_architecture,
    evaluate_constraints,
    freeze_architecture,
    generate_candidates,
    load_architecture_contract,
    run_sensitivity_analysis,
    score_candidates,
    verify_architecture_freeze,
    evaluate_durability,
    build_evolution_contract,
    verify_evolution_contract,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/architecture_decisioning/kernel_contract.v2.json"

EXPECTED_MODULES = (
    "factory/architecture_decisioning/__init__.py",
    "factory/architecture_decisioning/canonical.py",
    "factory/architecture_decisioning/models.py",
    "factory/architecture_decisioning/driver_compiler.py",
    "factory/architecture_decisioning/registry.py",
    "factory/architecture_decisioning/constraints.py",
    "factory/architecture_decisioning/scoring.py",
    "factory/architecture_decisioning/sensitivity.py",
    "factory/architecture_decisioning/risk.py",
    "factory/architecture_decisioning/freeze.py",
    "factory/architecture_decisioning/engine.py",
    "factory/architecture_decisioning/evidence.py",
    "factory/architecture_decisioning/durability.py",
)

REQ_SHA = "a" * 64

def observations() -> list[dict[str, Any]]:
    return [
        {
            "driver_id": "transaction_consistency",
            "source_class": "EXPLICIT_REQUIREMENT",
            "value": "strong_single_case_consistency",
            "confidence": 1.0,
            "hard_constraint": True,
            "evidence": ["REQ-TXN-001"],
        },
        {
            "driver_id": "auditability",
            "source_class": "EXPLICIT_REQUIREMENT",
            "value": "append_only_evidence_required",
            "confidence": 1.0,
            "hard_constraint": True,
            "evidence": ["REQ-EVD-002"],
        },
        {
            "driver_id": "business_criticality",
            "source_class": "DERIVED_STRONG",
            "value": "regulated_customer_harm_resolution",
            "confidence": 0.9,
            "hard_constraint": False,
            "evidence": ["REQ-BIZ-003"],
        },
    ]

def local_context() -> dict[str, Any]:
    return {
        "local_only": True,
        "mock_only": True,
        "real_payment_calls": "disabled",
        "allow_external_infrastructure": False,
        "acceptance_bar_delta": 0.0,
        "material_trust_boundary_change": False,
    }

def load() -> dict[str, Any]:
    return load_architecture_contract(CONTRACT_PATH)

def test_expected_module_layout_exists() -> None:
    assert all((ROOT / rel).is_file() for rel in EXPECTED_MODULES)

def test_contract_load_is_deterministic_and_complete() -> None:
    first = load()
    second = load()
    assert first == second
    assert first["schema_version"] == "upi-app-factory.architecture-decision-durability-kernel-contract.v2"
    assert len(first["patterns"]) == 5
    assert len(first["required_driver_ids"]) >= 12
    assert sum(first["default_weights"].values()) == 100
    assert first["contract_digest"] == canonical_sha256({k: v for k, v in first.items() if k != "contract_digest"})

def test_driver_ir_preserves_evidence_and_never_fabricates_missing_nfrs() -> None:
    ir = compile_driver_ir(REQ_SHA, observations(), load())
    by_id = {row["driver_id"]: row for row in ir["drivers"]}
    assert by_id["transaction_consistency"]["source_class"] == "EXPLICIT_REQUIREMENT"
    assert by_id["transaction_consistency"]["value"] == "strong_single_case_consistency"
    assert by_id["transaction_consistency"]["evidence"] == ["REQ-TXN-001"]
    assert by_id["peak_tps"]["source_class"] == "UNKNOWN"
    assert by_id["peak_tps"]["value"] is None
    assert by_id["latency_slo_ms"]["source_class"] == "UNKNOWN"
    assert by_id["latency_slo_ms"]["value"] is None
    assert ir["requirements_sha256"] == REQ_SHA
    assert ir["digest"] == canonical_sha256({k: v for k, v in ir.items() if k != "digest"})

def test_driver_ir_rejects_unknown_driver_and_bad_source_class() -> None:
    bad = observations() + [{"driver_id": "invented_tps", "source_class": "ASSUMPTION", "value": 9999}]
    with pytest.raises(ArchitectureDecisionError):
        compile_driver_ir(REQ_SHA, bad, load())
    bad2 = observations()
    bad2[0] = {**bad2[0], "source_class": "LLM_GUESS"}
    with pytest.raises(ArchitectureDecisionError):
        compile_driver_ir(REQ_SHA, bad2, load())

def test_candidate_generation_is_bounded_diverse_and_deterministic() -> None:
    ir = compile_driver_ir(REQ_SHA, observations(), load())
    a = generate_candidates(ir, load())
    b = generate_candidates(ir, load())
    assert a == b
    ids = [row["pattern_id"] for row in a]
    assert 3 <= len(ids) <= 5
    assert len(ids) == len(set(ids))
    assert "MODULAR_MONOLITH_HEXAGONAL" in ids
    assert "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX" in ids
    assert "SERVICE_ORIENTED_DISTRIBUTED" in ids

def test_hard_constraints_precede_scoring() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    candidates = generate_candidates(ir, contract)
    by_id = {row["pattern_id"]: row for row in candidates}
    modular = evaluate_constraints(by_id["MODULAR_MONOLITH_HEXAGONAL"], contract, local_context())
    service = evaluate_constraints(by_id["SERVICE_ORIENTED_DISTRIBUTED"], contract, local_context())
    cqrs = evaluate_constraints(by_id["CQRS_EVENT_ORIENTED"], contract, local_context())
    assert modular["outcome"] == "ALLOW"
    assert service["outcome"] == "HUMAN_GATE"
    assert cqrs["outcome"] == "ANALYSIS_ONLY"

def test_prohibited_technology_is_rejected_even_if_candidate_otherwise_good() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    candidate = deepcopy(generate_candidates(ir, contract)[0])
    candidate["required_technologies"] = [*candidate["required_technologies"], "live_payment_rail"]
    result = evaluate_constraints(candidate, contract, local_context())
    assert result["outcome"] == "REJECT"

def test_negative_acceptance_bar_delta_is_never_score_compensable() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    candidate = generate_candidates(ir, contract)[0]
    context = {**local_context(), "acceptance_bar_delta": -0.01}
    result = evaluate_constraints(candidate, contract, context)
    assert result["outcome"] == "REJECT"

def test_scoring_is_deterministic_and_rejects_invalid_weights() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    candidates = generate_candidates(ir, contract)
    scores1 = score_candidates(candidates, contract["default_weights"], {})
    scores2 = score_candidates(candidates, contract["default_weights"], {})
    assert scores1 == scores2
    assert scores1 == sorted(scores1, key=lambda x: (-x["total_score"], x["pattern_id"]))
    bad = dict(contract["default_weights"])
    bad["scalability"] += 1
    with pytest.raises(ArchitectureDecisionError):
        score_candidates(candidates, bad, {})

def test_default_local_decision_selects_an_executable_candidate() -> None:
    decision = decide_architecture(
        requirements_sha256=REQ_SHA,
        observations=observations(),
        contract=load(),
        context=local_context(),
        weights=None,
        dimension_overrides=None,
    )
    assert decision["decision_status"] == "SELECTED"
    assert decision["selected_execution_state"] == "EXECUTABLE"
    assert decision["authority_class"] in {"A0", "A1", "A2", "A3"}
    assert decision["decision_digest"] == canonical_sha256({k: v for k, v in decision.items() if k != "decision_digest"})

def test_no_silent_fallback_when_highest_scoring_option_requires_human_authority() -> None:
    contract = load()
    overrides = {
        "SERVICE_ORIENTED_DISTRIBUTED": {dimension: 100 for dimension in contract["score_dimensions"]},
        "MODULAR_MONOLITH_HEXAGONAL": {dimension: 60 for dimension in contract["score_dimensions"]},
        "WORKFLOW_CENTRIC_MODULAR_MONOLITH": {dimension: 60 for dimension in contract["score_dimensions"]},
        "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX": {dimension: 60 for dimension in contract["score_dimensions"]},
        "CQRS_EVENT_ORIENTED": {dimension: 60 for dimension in contract["score_dimensions"]},
    }
    decision = decide_architecture(
        requirements_sha256=REQ_SHA,
        observations=observations(),
        contract=contract,
        context=local_context(),
        weights=None,
        dimension_overrides=overrides,
    )
    assert decision["selected_candidate_id"] == "SERVICE_ORIENTED_DISTRIBUTED"
    assert decision["decision_status"] == "HUMAN_GATE"
    assert decision["authority_class"] == "A4"

def test_analysis_only_winner_becomes_factory_capability_gap_not_fallback() -> None:
    contract = load()
    overrides = {
        "CQRS_EVENT_ORIENTED": {dimension: 100 for dimension in contract["score_dimensions"]},
        "MODULAR_MONOLITH_HEXAGONAL": {dimension: 55 for dimension in contract["score_dimensions"]},
        "WORKFLOW_CENTRIC_MODULAR_MONOLITH": {dimension: 55 for dimension in contract["score_dimensions"]},
        "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX": {dimension: 55 for dimension in contract["score_dimensions"]},
        "SERVICE_ORIENTED_DISTRIBUTED": {dimension: 50 for dimension in contract["score_dimensions"]},
    }
    decision = decide_architecture(
        requirements_sha256=REQ_SHA,
        observations=observations(),
        contract=contract,
        context=local_context(),
        weights=None,
        dimension_overrides=overrides,
    )
    assert decision["selected_candidate_id"] == "CQRS_EVENT_ORIENTED"
    assert decision["decision_status"] == "FACTORY_CAPABILITY_GAP"

def test_authority_classification_is_explicit() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    by_id = {row["pattern_id"]: row for row in generate_candidates(ir, contract)}
    modular_constraints = evaluate_constraints(by_id["MODULAR_MONOLITH_HEXAGONAL"], contract, local_context())
    service_constraints = evaluate_constraints(by_id["SERVICE_ORIENTED_DISTRIBUTED"], contract, local_context())
    assert classify_authority(by_id["MODULAR_MONOLITH_HEXAGONAL"], modular_constraints, local_context(), contract) == "A3"
    assert classify_authority(by_id["SERVICE_ORIENTED_DISTRIBUTED"], service_constraints, local_context(), contract) == "A4"

def test_sensitivity_reports_conditional_winner_when_assumptions_change() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    candidates = generate_candidates(ir, contract)
    scale_weights = {
        "business_correctness": 7,
        "payment_integrity": 7,
        "auditability": 5,
        "security": 5,
        "reliability": 10,
        "operability": 4,
        "maintainability": 3,
        "performance": 18,
        "scalability": 22,
        "testability": 2,
        "deployment_simplicity": 1,
        "cost_efficiency": 1,
        "vendor_portability": 2,
        "evolvability": 5,
        "reversibility": 4,
        "upgradeability": 4,
    }
    result = run_sensitivity_analysis(
        candidates=candidates,
        base_weights=contract["default_weights"],
        scenarios=[{"scenario_id": "scale_heavy", "weights": scale_weights}],
        dimension_overrides={},
    )
    assert result["base_winner"]
    assert result["scenarios"][0]["winner"]
    assert result["winner_stability"] in {"STABLE", "CONDITIONAL"}
    assert result["digest"] == canonical_sha256({k: v for k, v in result.items() if k != "digest"})

def test_freeze_binds_requirements_driver_contract_and_decision() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    decision = decide_architecture(
        requirements_sha256=REQ_SHA,
        observations=observations(),
        contract=contract,
        context=local_context(),
        weights=None,
        dimension_overrides=None,
    )
    freeze = freeze_architecture(
        decision=decision,
        driver_ir=ir,
        contract=contract,
        requirements_sha256=REQ_SHA,
    )
    assert freeze["requirements_sha256"] == REQ_SHA
    assert freeze["driver_ir_digest"] == ir["digest"]
    assert freeze["contract_digest"] == contract["contract_digest"]
    assert freeze["decision_digest"] == decision["decision_digest"]
    assert freeze["freeze_digest"] == canonical_sha256({k: v for k, v in freeze.items() if k != "freeze_digest"})
    assert verify_architecture_freeze(freeze, decision, ir, contract, REQ_SHA) is True
    assert verify_architecture_freeze(freeze, decision, ir, contract, "b" * 64) is False

def test_freeze_refuses_human_gate_and_capability_gap() -> None:
    contract = load()
    human_overrides = {
        "SERVICE_ORIENTED_DISTRIBUTED": {dimension: 100 for dimension in contract["score_dimensions"]},
    }
    human = decide_architecture(
        requirements_sha256=REQ_SHA, observations=observations(), contract=contract,
        context=local_context(), weights=None, dimension_overrides=human_overrides,
    )
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    with pytest.raises(ArchitectureHumanGate):
        freeze_architecture(human, ir, contract, REQ_SHA)

    gap_overrides = {
        "CQRS_EVENT_ORIENTED": {dimension: 100 for dimension in contract["score_dimensions"]},
        "MODULAR_MONOLITH_HEXAGONAL": {dimension: 1 for dimension in contract["score_dimensions"]},
        "WORKFLOW_CENTRIC_MODULAR_MONOLITH": {dimension: 1 for dimension in contract["score_dimensions"]},
        "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX": {dimension: 1 for dimension in contract["score_dimensions"]},
        "SERVICE_ORIENTED_DISTRIBUTED": {dimension: 1 for dimension in contract["score_dimensions"]},
    }
    gap = decide_architecture(
        requirements_sha256=REQ_SHA, observations=observations(), contract=contract,
        context=local_context(), weights=None, dimension_overrides=gap_overrides,
    )
    assert gap["decision_status"] == "FACTORY_CAPABILITY_GAP"
    with pytest.raises(ArchitectureDecisionError):
        freeze_architecture(gap, ir, contract, REQ_SHA)


def test_time_resilience_is_a_first_class_contract_property() -> None:
    contract = load()
    policy = contract["durability_evolution_policy"]
    assert len(policy["required_controls"]) >= 12
    assert policy["silent_breaking_change"] == "REJECT"
    assert policy["silent_dependency_eol"] == "REJECT"
    assert policy["silent_provider_lock_in"] == "REJECT"
    assert contract["freeze_policy"]["require_durability_pass"] is True
    assert contract["freeze_policy"]["bind_evolution_contract_digest"] is True
    assert {"evolvability", "reversibility", "upgradeability"} <= set(contract["score_dimensions"])
    assert sum(contract["default_weights"].values()) == 100


def test_future_facing_drivers_remain_unknown_when_requirements_are_silent() -> None:
    ir = compile_driver_ir(REQ_SHA, observations(), load())
    by_id = {row["driver_id"]: row for row in ir["drivers"]}
    for driver_id in (
        "compatibility_horizon_years",
        "change_frequency",
        "api_evolution",
        "schema_evolution",
        "event_contract_evolution",
        "dependency_support_policy",
        "model_provider_replaceability",
        "crypto_agility",
        "migration_rollback_requirements",
        "deprecation_policy",
        "reproducibility_horizon",
    ):
        assert by_id[driver_id]["source_class"] == "UNKNOWN"
        assert by_id[driver_id]["value"] is None


def test_every_pattern_has_complete_durability_scoring_and_controls() -> None:
    contract = load()
    dims = set(contract["score_dimensions"])
    required = set(contract["durability_evolution_policy"]["required_controls"])
    for pattern in contract["patterns"]:
        assert set(pattern["base_scores"]) == dims
        assert set(pattern["durability_controls"]) >= required
        assert pattern["reconsideration_triggers"]


def test_durability_gate_fails_closed_when_required_control_is_removed() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    candidate = deepcopy(generate_candidates(ir, contract)[0])
    ok = evaluate_durability(candidate, ir, contract)
    assert ok["status"] == "PASS"
    candidate["durability_controls"] = candidate["durability_controls"][1:]
    bad = evaluate_durability(candidate, ir, contract)
    assert bad["status"] == "FAIL"
    assert bad["missing_controls"]


def test_evolution_contract_is_deterministic_and_identity_bound() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    decision = decide_architecture(
        requirements_sha256=REQ_SHA,
        observations=observations(),
        contract=contract,
        context=local_context(),
        weights=None,
        dimension_overrides=None,
    )
    evo1 = build_evolution_contract(decision, ir, contract)
    evo2 = build_evolution_contract(decision, ir, contract)
    assert evo1 == evo2
    assert evo1["requirements_sha256"] == REQ_SHA
    assert evo1["driver_ir_digest"] == ir["digest"]
    assert evo1["contract_digest"] == contract["contract_digest"]
    assert evo1["decision_digest"] == decision["decision_digest"]
    assert evo1["reconsideration_triggers"]
    assert evo1["compatibility_policy"]
    assert evo1["migration_policy"]
    assert evo1["dependency_policy"]
    assert evo1["provider_model_policy"]
    assert evo1["security_agility_policy"]
    assert evo1["evidence_continuity_policy"]
    assert evo1["digest"] == canonical_sha256({k: v for k, v in evo1.items() if k != "digest"})
    assert verify_evolution_contract(evo1, decision, ir, contract) is True
    tampered = deepcopy(evo1)
    tampered["decision_digest"] = "0" * 64
    assert verify_evolution_contract(tampered, decision, ir, contract) is False


def test_architecture_freeze_binds_evolution_contract_digest() -> None:
    contract = load()
    ir = compile_driver_ir(REQ_SHA, observations(), contract)
    decision = decide_architecture(
        requirements_sha256=REQ_SHA,
        observations=observations(),
        contract=contract,
        context=local_context(),
        weights=None,
        dimension_overrides=None,
    )
    evo = build_evolution_contract(decision, ir, contract)
    freeze = freeze_architecture(decision, ir, contract, REQ_SHA)
    assert freeze["evolution_contract_digest"] == evo["digest"]
    assert verify_architecture_freeze(freeze, decision, ir, contract, REQ_SHA) is True
    bad = deepcopy(freeze)
    bad["evolution_contract_digest"] = "0" * 64
    assert verify_architecture_freeze(bad, decision, ir, contract, REQ_SHA) is False
