"""Deterministic durability evaluation and evolution identity binding."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import canonical_sha256
from .models import ArchitectureDecisionError, require_sha256

V2_SCHEMA = "upi-app-factory.architecture-decision-durability-kernel-contract.v2"


def _valid_digest(document: Mapping[str, Any], field: str) -> bool:
    supplied = document.get(field)
    body = {key: value for key, value in document.items() if key != field}
    return isinstance(supplied, str) and supplied == canonical_sha256(body)


def evaluate_durability(
    candidate: Mapping[str, Any],
    driver_ir: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless a V2 candidate carries every durability obligation."""
    policy = contract.get("durability_evolution_policy")
    if contract.get("schema_version") != V2_SCHEMA or not isinstance(policy, Mapping):
        raise ArchitectureDecisionError("durability evaluation requires a V2 contract")
    if not _valid_digest(driver_ir, "digest"):
        raise ArchitectureDecisionError("driver IR digest is invalid")
    required = policy.get("required_controls")
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ArchitectureDecisionError("required durability controls are invalid")
    actual = candidate.get("durability_controls", [])
    actual_set = set(actual) if isinstance(actual, list) else set()
    missing = sorted(set(required).difference(actual_set))
    triggers = candidate.get("reconsideration_triggers")
    has_triggers = isinstance(triggers, list) and bool(triggers) and all(
        isinstance(trigger, str) and bool(trigger) for trigger in triggers
    )
    result: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-durability-evaluation.v1",
        "pattern_id": candidate.get("pattern_id"),
        "driver_ir_digest": driver_ir.get("digest"),
        "contract_digest": contract.get("contract_digest"),
        "status": "PASS" if not missing and has_triggers else "FAIL",
        "missing_controls": missing,
        "reconsideration_triggers_present": has_triggers,
    }
    result["digest"] = canonical_sha256(result)
    return result


def build_evolution_contract(
    decision: Mapping[str, Any],
    driver_ir: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the reproducible V2 evolution contract for the selected pattern."""
    if contract.get("schema_version") != V2_SCHEMA:
        raise ArchitectureDecisionError("evolution contract requires a V2 contract")
    if (
        decision.get("decision_status") != "SELECTED"
        or decision.get("selected_execution_state") != "EXECUTABLE"
    ):
        raise ArchitectureDecisionError("evolution contract requires a selected executable decision")
    if not _valid_digest(decision, "decision_digest"):
        raise ArchitectureDecisionError("decision digest is invalid")
    if not _valid_digest(driver_ir, "digest"):
        raise ArchitectureDecisionError("driver IR digest is invalid")
    if not _valid_digest(contract, "contract_digest"):
        raise ArchitectureDecisionError("contract digest is invalid")
    requirements_sha256 = require_sha256(
        decision.get("requirements_sha256"), "requirements_sha256"
    )
    if (
        driver_ir.get("requirements_sha256") != requirements_sha256
        or decision.get("driver_ir_digest") != driver_ir.get("digest")
        or decision.get("contract_digest") != contract.get("contract_digest")
    ):
        raise ArchitectureDecisionError("evolution contract identity binding mismatch")
    selected_id = decision.get("selected_candidate_id")
    candidates = [
        pattern for pattern in contract.get("patterns", [])
        if isinstance(pattern, Mapping) and pattern.get("pattern_id") == selected_id
    ]
    if len(candidates) != 1:
        raise ArchitectureDecisionError("selected architecture is not in the V2 registry")
    candidate = candidates[0]
    durability = evaluate_durability(candidate, driver_ir, contract)
    if durability["status"] != "PASS":
        raise ArchitectureDecisionError("selected architecture fails durability policy")
    policy = contract["durability_evolution_policy"]
    result: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-evolution-contract.v1",
        "selected_candidate_id": selected_id,
        "requirements_sha256": requirements_sha256,
        "driver_ir_digest": driver_ir.get("digest"),
        "contract_digest": contract.get("contract_digest"),
        "decision_digest": decision.get("decision_digest"),
        "compatibility_policy": policy.get("public_contract_policy"),
        "migration_policy": policy.get("migration_policy"),
        "dependency_policy": policy.get("dependency_policy"),
        "provider_model_policy": policy.get("provider_model_policy"),
        "security_agility_policy": policy.get("security_policy"),
        "reconsideration_triggers": candidate.get("reconsideration_triggers"),
        "evidence_continuity_policy": policy.get("evidence_continuity_policy"),
        "durability_evaluation_digest": durability["digest"],
    }
    result["digest"] = canonical_sha256(result)
    return result


def verify_evolution_contract(
    evolution_contract: Mapping[str, Any],
    decision: Mapping[str, Any],
    driver_ir: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> bool:
    """Verify content and all transitive identity bindings by reconstruction."""
    try:
        expected = build_evolution_contract(decision, driver_ir, contract)
    except ArchitectureDecisionError:
        return False
    return dict(evolution_contract) == expected
