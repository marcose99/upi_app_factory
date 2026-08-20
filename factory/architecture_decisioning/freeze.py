"""Architecture freeze creation and binding verification."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import canonical_sha256
from .durability import V2_SCHEMA, build_evolution_contract
from .models import ArchitectureDecisionError, ArchitectureHumanGate, require_sha256


def freeze_architecture(
    decision: Mapping[str, Any], driver_ir: Mapping[str, Any],
    contract: Mapping[str, Any], requirements_sha256: str,
) -> dict[str, Any]:
    require_sha256(requirements_sha256, "requirements_sha256")
    decision_body = {key: value for key, value in decision.items() if key != "decision_digest"}
    if decision.get("decision_digest") != canonical_sha256(decision_body):
        raise ArchitectureDecisionError("decision digest is invalid")
    driver_body = {key: value for key, value in driver_ir.items() if key != "digest"}
    if driver_ir.get("digest") != canonical_sha256(driver_body):
        raise ArchitectureDecisionError("driver IR digest is invalid")
    contract_body = {key: value for key, value in contract.items() if key != "contract_digest"}
    if contract.get("contract_digest") != canonical_sha256(contract_body):
        raise ArchitectureDecisionError("contract digest is invalid")
    status = decision.get("decision_status")
    if status == "HUMAN_GATE":
        raise ArchitectureHumanGate("architecture decision requires human enablement")
    if status != "SELECTED":
        raise ArchitectureDecisionError("only SELECTED decisions may be frozen")
    if decision.get("selected_execution_state") != "EXECUTABLE":
        raise ArchitectureDecisionError("only executable patterns may be frozen")
    classes = contract.get("authority_classes", [])
    authority = decision.get("authority_class")
    if authority not in classes or classes.index(authority) > classes.index("A3"):
        raise ArchitectureHumanGate("architecture authority exceeds automatic A3 limit")
    if decision.get("requirements_sha256") != requirements_sha256:
        raise ArchitectureDecisionError("decision requirements binding does not match")
    if driver_ir.get("requirements_sha256") != requirements_sha256:
        raise ArchitectureDecisionError("driver IR requirements binding does not match")
    if decision.get("driver_ir_digest") != driver_ir.get("digest"):
        raise ArchitectureDecisionError("decision driver IR binding does not match")
    if decision.get("contract_digest") != contract.get("contract_digest"):
        raise ArchitectureDecisionError("decision contract binding does not match")
    freeze: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-freeze.v1",
        "selected_candidate_id": decision.get("selected_candidate_id"),
        "authority_class": authority,
        "requirements_sha256": requirements_sha256,
        "driver_ir_digest": driver_ir.get("digest"),
        "contract_digest": contract.get("contract_digest"),
        "decision_digest": decision.get("decision_digest"),
    }
    if contract.get("schema_version") == V2_SCHEMA:
        evolution = build_evolution_contract(decision, driver_ir, contract)
        freeze["schema_version"] = "upi-app-factory.architecture-freeze.v2"
        freeze["evolution_contract_digest"] = evolution["digest"]
    freeze["freeze_digest"] = canonical_sha256(freeze)
    return freeze


def verify_architecture_freeze(
    freeze: Mapping[str, Any], decision: Mapping[str, Any], driver_ir: Mapping[str, Any],
    contract: Mapping[str, Any], requirements_sha256: str,
) -> bool:
    try:
        require_sha256(requirements_sha256, "requirements_sha256")
        expected = freeze_architecture(decision, driver_ir, contract, requirements_sha256)
    except ArchitectureDecisionError:
        return False
    return dict(freeze) == expected
