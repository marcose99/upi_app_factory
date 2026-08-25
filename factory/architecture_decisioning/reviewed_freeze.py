"""Reviewed architecture freeze and transitive package verification."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .adjudication import adjudicate_architecture_reviews
from .canonical import canonical_sha256
from .durability import build_evolution_contract
from .models import ArchitectureDecisionError, ArchitectureHumanGate, require_sha256
from .prototype_resolution import (
    HUMAN_RESOLUTION_STATUS,
    verify_human_resolved_adjudication,
)


def _valid_digest(value: Mapping[str, Any], field: str) -> bool:
    digest = value.get(field)
    return isinstance(digest, str) and digest == canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def _contract_pattern(contract: Mapping[str, Any], selected: str) -> Mapping[str, Any]:
    matches = [
        row for row in contract.get("patterns", [])
        if isinstance(row, Mapping) and row.get("pattern_id") == selected
    ]
    if len(matches) != 1:
        unsupported = contract.get("unsupported_patterns", {})
        disposition = unsupported.get(selected) if isinstance(unsupported, Mapping) else None
        if disposition == "HUMAN_GATE":
            raise ArchitectureHumanGate("selected architecture requires human enablement")
        raise ArchitectureDecisionError("selected architecture has no realization adapter")
    return matches[0]


def _reviewed_decision(
    upstream: Mapping[str, Any], adjudication: Mapping[str, Any],
    architecture_contract: Mapping[str, Any], realization_contract: Mapping[str, Any],
) -> dict[str, Any]:
    selected = adjudication.get("selected_candidate_id")
    if not isinstance(selected, str):
        raise ArchitectureDecisionError("review adjudication has no selected candidate")
    realization = _contract_pattern(realization_contract, selected)
    architecture = [
        row for row in architecture_contract.get("patterns", [])
        if isinstance(row, Mapping) and row.get("pattern_id") == selected
    ]
    if len(architecture) != 1 or realization.get("execution_state") != "EXECUTABLE":
        raise ArchitectureDecisionError("reviewed candidate is not executable")
    constraints = upstream.get("constraints")
    if not isinstance(constraints, Mapping) or not isinstance(constraints.get(selected), Mapping):
        raise ArchitectureDecisionError("reviewed candidate constraint evidence is missing")
    if constraints[selected].get("outcome") != "ALLOW":
        raise ArchitectureDecisionError("reviewed candidate is not constraint-authorized")
    authority = realization.get("automatic_authority_class")
    allowed = realization_contract.get("automatic_authority_classes", [])
    if not isinstance(allowed, list) or authority not in allowed or allowed.index(authority) > allowed.index("A3"):
        raise ArchitectureHumanGate("reviewed architecture exceeds automatic A3 authority")
    decision = deepcopy(dict(upstream))
    decision.update({
        "schema_version": "upi-app-factory.architecture-reviewed-decision.v1",
        "upstream_decision_digest": upstream.get("decision_digest"),
        "adjudication_digest": adjudication.get("adjudication_digest"),
        "selected_candidate_id": selected,
        "selected_execution_state": "EXECUTABLE",
        "decision_status": "SELECTED",
        "authority_class": authority,
    })
    resolution = adjudication.get("human_resolution")
    if isinstance(resolution, Mapping):
        decision.update({
            "governance_resolution_status": HUMAN_RESOLUTION_STATUS,
            "human_resolution_digest": resolution.get("human_resolution_digest"),
        })
    decision.pop("decision_digest", None)
    decision["reviewed_decision_digest"] = canonical_sha256(decision)
    return decision


def freeze_reviewed_architecture(
    *, upstream_decision: Mapping[str, Any], driver_ir: Mapping[str, Any],
    architecture_contract: Mapping[str, Any], review_contract: Mapping[str, Any],
    architecture_packet: Mapping[str, Any], review_set: Mapping[str, Any],
    adjudication: Mapping[str, Any], realization_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed and freeze the independently reviewed winner."""
    documents = (
        (upstream_decision, "decision_digest"), (driver_ir, "digest"),
        (architecture_contract, "contract_digest"), (review_contract, "contract_digest"),
        (architecture_packet, "packet_digest"), (review_set, "review_set_digest"),
        (adjudication, "adjudication_digest"), (realization_contract, "contract_digest"),
    )
    if any(not _valid_digest(document, field) for document, field in documents):
        raise ArchitectureDecisionError("reviewed architecture identity digest is invalid")
    status = adjudication.get("status")
    if status == "HUMAN_GATE":
        raise ArchitectureHumanGate("architecture review requires human enablement")
    if status != realization_contract.get("required_adjudication_status"):
        raise ArchitectureDecisionError("only SELECTED_REVIEWED adjudications may be frozen")
    if upstream_decision.get("decision_status") in {
        "HUMAN_GATE", "PROTOTYPE_REQUIRED", "FACTORY_CAPABILITY_GAP", "NO_ADMISSIBLE"
    }:
        raise ArchitectureDecisionError("non-bypassable upstream status cannot be frozen")

    confidence = adjudication.get("confidence")
    if not isinstance(confidence, Mapping) or not _valid_digest(confidence, "digest"):
        raise ArchitectureDecisionError("review confidence identity is invalid")
    order = realization_contract.get("confidence_order")
    minimum = realization_contract.get("minimum_review_confidence_level")
    level = confidence.get("level")
    if not isinstance(order, list) or level not in order or minimum not in order:
        raise ArchitectureDecisionError("review confidence policy is invalid")
    below_minimum = order.index(level) < order.index(minimum)
    if below_minimum and not isinstance(adjudication.get("human_resolution"), Mapping):
        raise ArchitectureHumanGate("review confidence is below the governed minimum")

    deterministic_adjudication = adjudicate_architecture_reviews(
        dict(architecture_packet),
        dict(review_set),
        dict(review_contract),
        dict(architecture_contract),
    )
    automatic_status = deterministic_adjudication.get("status")
    human_resolved = False
    if automatic_status == "SELECTED_REVIEWED":
        if dict(adjudication) != deterministic_adjudication:
            raise ArchitectureDecisionError(
                "selected adjudication does not match deterministic review result"
            )
    elif automatic_status == "PROTOTYPE_REQUIRED":
        human_resolved = verify_human_resolved_adjudication(
            adjudication,
            deterministic_pre_resolution=deterministic_adjudication,
            packet=architecture_packet,
            review_set=review_set,
            review_contract=review_contract,
            requirements_sha256=str(upstream_decision.get("requirements_sha256")),
        )
        if not human_resolved:
            raise ArchitectureHumanGate(
                "prototype-required architecture lacks a valid human resolution"
            )
    elif automatic_status == "HUMAN_GATE":
        raise ArchitectureHumanGate("architecture review requires human enablement")
    else:
        raise ArchitectureDecisionError(
            f"deterministic architecture review cannot be frozen: {automatic_status}"
        )
    if (
        architecture_packet.get("decision_digest") != upstream_decision.get("decision_digest")
        or architecture_packet.get("driver_ir_digest") != driver_ir.get("digest")
        or architecture_packet.get("architecture_contract_digest") != architecture_contract.get("contract_digest")
        or architecture_packet.get("review_contract_digest") != review_contract.get("contract_digest")
        or review_set.get("architecture_packet_digest") != architecture_packet.get("packet_digest")
        or adjudication.get("architecture_packet_digest") != architecture_packet.get("packet_digest")
        or adjudication.get("review_set_digest") != review_set.get("review_set_digest")
    ):
        raise ArchitectureDecisionError("reviewed architecture transitive binding mismatch")
    if below_minimum and not human_resolved:
        raise ArchitectureHumanGate("review confidence is below the governed minimum")
    reviewed = _reviewed_decision(
        upstream_decision, adjudication, architecture_contract, realization_contract
    )
    evolution_input = deepcopy(reviewed)
    evolution_input["decision_digest"] = evolution_input.pop("reviewed_decision_digest")
    evolution = build_evolution_contract(evolution_input, driver_ir, architecture_contract)
    selected = str(reviewed["selected_candidate_id"])
    adapter = _contract_pattern(realization_contract, selected)
    freeze: dict[str, Any] = {
        "schema_version": "upi-app-factory.reviewed-architecture-freeze.v1",
        "requirements_sha256": require_sha256(upstream_decision.get("requirements_sha256"), "requirements_sha256"),
        "driver_ir_digest": driver_ir.get("digest"),
        "architecture_contract_digest": architecture_contract.get("contract_digest"),
        "review_contract_digest": review_contract.get("contract_digest"),
        "architecture_packet_digest": architecture_packet.get("packet_digest"),
        "review_set_digest": review_set.get("review_set_digest"),
        "adjudication_digest": adjudication.get("adjudication_digest"),
        "reviewed_decision_digest": reviewed.get("reviewed_decision_digest"),
        "evolution_contract_digest": evolution.get("digest"),
        "realization_contract_digest": realization_contract.get("contract_digest"),
        "selected_candidate_id": selected,
        "adapter_id": adapter.get("adapter_id"),
        "confidence_digest": confidence.get("digest"),
    }
    if human_resolved:
        resolution = adjudication.get("human_resolution")
        if not isinstance(resolution, Mapping):
            raise ArchitectureDecisionError("human resolution evidence is missing")
        freeze.update({
            "governance_resolution_status": HUMAN_RESOLUTION_STATUS,
            "human_resolution_digest": resolution.get("human_resolution_digest"),
        })
    freeze["freeze_digest"] = canonical_sha256(freeze)
    return freeze


def build_reviewed_architecture_package(**kwargs: Mapping[str, Any]) -> dict[str, Any]:
    freeze = freeze_reviewed_architecture(**kwargs)
    upstream = kwargs["upstream_decision"]
    reviewed = _reviewed_decision(
        upstream, kwargs["adjudication"], kwargs["architecture_contract"],
        kwargs["realization_contract"],
    )
    evolution_input = deepcopy(reviewed)
    evolution_input["decision_digest"] = evolution_input.pop("reviewed_decision_digest")
    evolution = build_evolution_contract(
        evolution_input, kwargs["driver_ir"], kwargs["architecture_contract"]
    )
    package: dict[str, Any] = {
        key: deepcopy(dict(value)) for key, value in kwargs.items()
    }
    package.update({"reviewed_decision": reviewed, "evolution_contract": evolution, "reviewed_freeze": freeze})
    package["package_digest"] = canonical_sha256(package)
    return package


def verify_reviewed_architecture_freeze(*, freeze: Mapping[str, Any], **kwargs: Mapping[str, Any]) -> bool:
    try:
        return dict(freeze) == freeze_reviewed_architecture(**kwargs)
    except ArchitectureDecisionError:
        return False


def verify_reviewed_architecture_package(package: Mapping[str, Any]) -> bool:
    try:
        if not _valid_digest(package, "package_digest"):
            return False
        names = (
            "upstream_decision", "driver_ir", "architecture_contract", "review_contract",
            "architecture_packet", "review_set", "adjudication", "realization_contract",
        )
        kwargs = {name: package[name] for name in names}
        expected = build_reviewed_architecture_package(**kwargs)
        return dict(package) == expected
    except (ArchitectureDecisionError, KeyError, TypeError):
        return False
