"""Compile normalized architecture driver IR without inventing missing NFRs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from .canonical import canonical_sha256, require_finite_number
from .models import ArchitectureDecisionError, require_sha256


def compile_driver_ir(
    requirements_sha256: str,
    observations: Iterable[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    require_sha256(requirements_sha256, "requirements_sha256")
    required_ids = contract.get("required_driver_ids")
    source_classes = contract.get("source_classes")
    if not isinstance(required_ids, list) or not isinstance(source_classes, list):
        raise ArchitectureDecisionError("contract driver definitions are invalid")
    if len(required_ids) != len(set(required_ids)):
        raise ArchitectureDecisionError("required driver IDs must be unique")
    observed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(observations):
        if not isinstance(item, Mapping):
            raise ArchitectureDecisionError(f"observation {index} must be an object")
        driver_id = item.get("driver_id")
        source_class = item.get("source_class")
        if not isinstance(driver_id, str) or driver_id not in required_ids:
            raise ArchitectureDecisionError(f"unknown driver_id: {driver_id}")
        if driver_id in observed:
            raise ArchitectureDecisionError(f"duplicate driver_id: {driver_id}")
        if source_class not in source_classes:
            raise ArchitectureDecisionError(f"invalid source_class for {driver_id}")
        confidence = item.get("confidence", 0.0 if source_class == "UNKNOWN" else 1.0)
        confidence_number = require_finite_number(confidence, f"confidence for {driver_id}")
        if not 0.0 <= confidence_number <= 1.0:
            raise ArchitectureDecisionError(f"confidence for {driver_id} must be between 0 and 1")
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(v, str) for v in evidence):
            raise ArchitectureDecisionError(f"evidence for {driver_id} must be a string list")
        value = item.get("value")
        if source_class == "UNKNOWN" and value is not None:
            raise ArchitectureDecisionError(f"UNKNOWN driver {driver_id} must have null value")
        observed[driver_id] = {
            "driver_id": driver_id,
            "source_class": source_class,
            "value": deepcopy(value),
            "confidence": confidence_number,
            "hard_constraint": bool(item.get("hard_constraint", False)),
            "evidence": deepcopy(evidence),
        }
    drivers = []
    for driver_id in required_ids:
        drivers.append(observed.get(driver_id, {
            "driver_id": driver_id, "source_class": "UNKNOWN", "value": None,
            "confidence": 0.0, "hard_constraint": False, "evidence": [],
        }))
    result: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-driver-ir.v1",
        "requirements_sha256": requirements_sha256,
        "drivers": drivers,
    }
    result["digest"] = canonical_sha256(result)
    return result
