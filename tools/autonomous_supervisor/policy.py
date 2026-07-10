from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.autonomous_supervisor.catalog import RepairCatalog


@dataclass(frozen=True)
class RepairRequest:
    gate: str
    attempt: int
    candidate_scope_verified: bool
    safe_fix_available: bool


@dataclass(frozen=True)
class RepairDecision:
    authorized: bool
    repair_id: str | None
    reason: str
    risk: str


class RepairPolicyEngine:
    def __init__(self, catalog: RepairCatalog) -> None:
        self.catalog = catalog

    def evaluate(self, request: RepairRequest) -> RepairDecision:
        rule = self.catalog.automatic_rule_for_gate(request.gate)
        if rule is None:
            return RepairDecision(
                authorized=False,
                repair_id=None,
                reason="NO_AUTOMATIC_RULE",
                risk="UNKNOWN",
            )
        if request.attempt > rule.max_attempts:
            return RepairDecision(
                authorized=False,
                repair_id=rule.repair_id,
                reason="ATTEMPT_LIMIT_EXCEEDED",
                risk=rule.risk,
            )
        if (
            rule.candidate_scope_required
            and not request.candidate_scope_verified
        ):
            return RepairDecision(
                authorized=False,
                repair_id=rule.repair_id,
                reason="CANDIDATE_SCOPE_NOT_VERIFIED",
                risk=rule.risk,
            )
        if rule.safe_fix_only and not request.safe_fix_available:
            return RepairDecision(
                authorized=False,
                repair_id=rule.repair_id,
                reason="SAFE_FIX_NOT_AVAILABLE",
                risk=rule.risk,
            )
        return RepairDecision(
            authorized=True,
            repair_id=rule.repair_id,
            reason="AUTHORIZED_BY_DECLARATIVE_POLICY",
            risk=rule.risk,
        )


def decision_to_object(decision: RepairDecision) -> dict[str, Any]:
    return {
        "authorized": decision.authorized,
        "repair_id": decision.repair_id,
        "reason": decision.reason,
        "risk": decision.risk,
    }
