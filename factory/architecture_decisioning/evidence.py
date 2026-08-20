"""Frozen architecture contract loading and validation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Union

from .canonical import canonical_sha256
from .models import ArchitectureDecisionError

PathLike = Union[str, Path]


def validate_contract(contract: dict[str, Any]) -> None:
    required = {
        "schema_version", "patterns", "technology_registry", "required_driver_ids",
        "source_classes", "score_dimensions", "default_weights", "authority_classes",
        "constraint_outcomes", "decision_statuses", "freeze_policy",
    }
    missing = sorted(required.difference(contract))
    if missing:
        raise ArchitectureDecisionError(f"contract missing fields: {', '.join(missing)}")
    supported_schemas = {
        "upi-app-factory.architecture-decision-kernel-contract.v1",
        "upi-app-factory.architecture-decision-durability-kernel-contract.v2",
    }
    if contract["schema_version"] not in supported_schemas:
        raise ArchitectureDecisionError("unsupported architecture contract schema")
    dimensions = contract["score_dimensions"]
    if (
        not isinstance(dimensions, list)
        or not dimensions
        or len(set(dimensions)) != len(dimensions)
    ):
        raise ArchitectureDecisionError("score_dimensions must be a unique non-empty list")
    weights = contract["default_weights"]
    if not isinstance(weights, dict) or set(weights) != set(dimensions):
        raise ArchitectureDecisionError("default_weights must cover score_dimensions exactly")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in weights.values()):
        raise ArchitectureDecisionError("default weights must be non-negative integers")
    if sum(weights.values()) != 100:
        raise ArchitectureDecisionError("default weights must sum to exactly 100")
    ids = [p.get("pattern_id") for p in contract["patterns"] if isinstance(p, dict)]
    if len(ids) != len(contract["patterns"]) or len(ids) != len(set(ids)):
        raise ArchitectureDecisionError("patterns must have unique pattern_id values")
    tech_ids = [
        technology.get("technology_id")
        for technology in contract["technology_registry"]
        if isinstance(technology, dict)
    ]
    if (
        len(tech_ids) != len(contract["technology_registry"])
        or len(tech_ids) != len(set(tech_ids))
    ):
        raise ArchitectureDecisionError("technology registry IDs must be unique")
    tech_set = set(tech_ids)
    for pattern in contract["patterns"]:
        if set(pattern.get("base_scores", {})) != set(dimensions):
            raise ArchitectureDecisionError(
                f"pattern {pattern.get('pattern_id')} has invalid scores"
            )
        if not set(pattern.get("required_technologies", [])).issubset(tech_set):
            raise ArchitectureDecisionError(
                f"pattern {pattern.get('pattern_id')} uses unknown technology"
            )
    if contract["schema_version"].endswith(".v2"):
        durability = contract.get("durability_evolution_policy")
        if not isinstance(durability, dict):
            raise ArchitectureDecisionError("V2 contract requires durability evolution policy")
        controls = durability.get("required_controls")
        if not isinstance(controls, list) or not controls or len(controls) != len(set(controls)):
            raise ArchitectureDecisionError("V2 required durability controls are invalid")
        for pattern in contract["patterns"]:
            if not set(controls).issubset(set(pattern.get("durability_controls", []))):
                raise ArchitectureDecisionError(
                    f"pattern {pattern.get('pattern_id')} lacks required durability controls"
                )
            if not pattern.get("reconsideration_triggers"):
                raise ArchitectureDecisionError(
                    f"pattern {pattern.get('pattern_id')} lacks reconsideration triggers"
                )


def load_architecture_contract(path: PathLike) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchitectureDecisionError(f"cannot load architecture contract: {exc}") from exc
    if not isinstance(raw, dict):
        raise ArchitectureDecisionError("architecture contract must be an object")
    contract = deepcopy(raw)
    supplied_digest = contract.pop("contract_digest", None)
    validate_contract(contract)
    digest = canonical_sha256(contract)
    if supplied_digest is not None and supplied_digest != digest:
        raise ArchitectureDecisionError("architecture contract digest is invalid")
    contract["contract_digest"] = digest
    return contract
