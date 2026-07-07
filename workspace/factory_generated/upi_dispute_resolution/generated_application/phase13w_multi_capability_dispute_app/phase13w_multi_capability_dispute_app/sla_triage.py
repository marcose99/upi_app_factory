"""Generated SLA triage capability."""
from __future__ import annotations

from .contracts import DisputeCase, EvidenceValidationResult, TriageDecision


def decide_triage(case: DisputeCase, evidence: EvidenceValidationResult) -> TriageDecision:
    reasons: list[str] = []
    if not evidence.accepted:
        reasons.append("evidence_validation_failed")
    if case.age_hours >= case.sla_hours:
        reasons.append("sla_breach_or_due")
    if case.amount_paise >= 100_000:
        reasons.append("high_value_dispute")

    if "evidence_validation_failed" in reasons:
        queue = "evidence_review"
    elif "sla_breach_or_due" in reasons:
        queue = "sla_escalation"
    else:
        queue = "standard_dispute_ops"

    return TriageDecision(
        case_id=case.case_id,
        queue=queue,
        needs_escalation=queue in {"evidence_review", "sla_escalation"},
        reasons=tuple(reasons),
    )
