from __future__ import annotations

from .contracts import DisputeTriageDecision, DisputeTriageRequest


TRIAGE_POLICY_ID = "POL-13V-DISPUTE-TRIAGE"
GOVERNED_REPAIR_POLICY_ID = "POL-13V-POLICY-GOVERNED-GENERATION"


def triage_dispute(request: DisputeTriageRequest) -> DisputeTriageDecision:
    """Policy-governed triage decision for locally generated UPI disputes."""
    if request.regulatory_complaint:
        return DisputeTriageDecision(
            dispute_id=request.dispute_id,
            action="ESCALATE",
            priority="CRITICAL",
            rationale="Regulatory complaint requires immediate governed escalation.",
            policy_ids=(TRIAGE_POLICY_ID, GOVERNED_REPAIR_POLICY_ID),
        )
    if (
        request.age_hours > 72
        or request.fraud_signal_score >= 85
        or request.amount_minor >= 100000
    ):
        return DisputeTriageDecision(
            dispute_id=request.dispute_id,
            action="SENIOR_REVIEW",
            priority="HIGH",
            rationale="High-risk dispute requires senior review before closure.",
            policy_ids=(TRIAGE_POLICY_ID, GOVERNED_REPAIR_POLICY_ID),
        )
    return DisputeTriageDecision(
        dispute_id=request.dispute_id,
        action="STANDARD_REVIEW",
        priority="NORMAL",
        rationale="Dispute remains in standard review queue.",
        policy_ids=(TRIAGE_POLICY_ID, GOVERNED_REPAIR_POLICY_ID),
    )
