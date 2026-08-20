"""Automatic authority classification."""

from __future__ import annotations

from typing import Any, Mapping

from .models import ArchitectureDecisionError


def classify_authority(
    candidate: Mapping[str, Any], constraints: Mapping[str, Any],
    context: Mapping[str, Any], contract: Mapping[str, Any],
) -> str:
    classes = contract.get("authority_classes", [])
    outcome = constraints.get("outcome")
    if outcome in {"HUMAN_GATE", "ANALYSIS_ONLY", "REJECT"}:
        authority = "A4"
    else:
        registry = {
            row["technology_id"]: row
            for row in contract.get("technology_registry", [])
        }
        floors = [
            registry[technology]["authority_floor"]
            for technology in candidate.get("required_technologies", [])
            if technology in registry
        ]
        authority = max(floors, key=classes.index, default="A0")
        if context.get("material_trust_boundary_change", False):
            authority = "A4"
    if authority not in classes:
        raise ArchitectureDecisionError("computed authority is absent from contract")
    return authority
