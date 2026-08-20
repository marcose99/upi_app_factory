"""Hard constraint evaluation with deterministic outcome precedence."""

from __future__ import annotations

from typing import Any, Mapping

from .models import ArchitectureDecisionError

_PRECEDENCE = {"ALLOW": 0, "ANALYSIS_ONLY": 1, "HUMAN_GATE": 2, "REJECT": 3}


def evaluate_constraints(
    candidate: Mapping[str, Any], contract: Mapping[str, Any], context: Mapping[str, Any]
) -> dict[str, Any]:
    technology_rows = contract.get("technology_registry", [])
    registry = {row["technology_id"]: row for row in technology_rows}
    findings: list[dict[str, str]] = []

    def add(outcome: str, reason: str) -> None:
        findings.append({"outcome": outcome, "reason": reason})

    required = candidate.get("required_technologies")
    if not isinstance(required, list):
        raise ArchitectureDecisionError("candidate required_technologies must be a list")
    for technology in required:
        row = registry.get(technology)
        if row is None:
            add("REJECT", f"unregistered_technology:{technology}")
        elif row.get("execution_state") == "PROHIBITED":
            add("REJECT", f"prohibited_technology:{technology}")
        elif row.get("execution_state") == "ANALYSIS_ONLY":
            add("ANALYSIS_ONLY", f"analysis_only_technology:{technology}")
        elif row.get("external_infrastructure") and not context.get(
            "allow_external_infrastructure", False
        ):
            add("HUMAN_GATE", f"external_infrastructure_without_authority:{technology}")
    state = candidate.get("execution_state")
    if state == "ANALYSIS_ONLY":
        add("ANALYSIS_ONLY", "analysis_only_pattern")
    elif state == "HUMAN_ENABLEMENT_REQUIRED":
        add("HUMAN_GATE", "human_enablement_required")
    elif state != "EXECUTABLE":
        add("REJECT", "invalid_execution_state")
    delta = context.get("acceptance_bar_delta", 0)
    if isinstance(delta, bool) or not isinstance(delta, (int, float)):
        raise ArchitectureDecisionError("acceptance_bar_delta must be numeric")
    if delta < 0:
        add("REJECT", "acceptance_bar_delta_negative")
    if context.get("real_payment_calls") != "disabled":
        add("REJECT", "real_payment_calls_not_disabled")
    if context.get("material_trust_boundary_change", False):
        add("HUMAN_GATE", "material_trust_boundary_change")
    outcome = max(
        (row["outcome"] for row in findings),
        key=lambda value: _PRECEDENCE[value],
        default="ALLOW",
    )
    return {"outcome": outcome, "findings": findings}
