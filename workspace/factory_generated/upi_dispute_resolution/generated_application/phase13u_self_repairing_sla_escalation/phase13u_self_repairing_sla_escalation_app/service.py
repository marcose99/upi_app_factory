from __future__ import annotations

from .contracts import SlaEscalationRequest, SlaEscalationResult


def validate_sla_escalation(request: SlaEscalationRequest) -> SlaEscalationResult:
    """Evaluate SLA breach status locally without external ecosystem calls."""

    remaining_minutes = request.sla_minutes - request.elapsed_minutes
    breach_detected = remaining_minutes < 0
    if breach_detected:
        status = "BREACHED"
        reason = "Elapsed minutes exceeded the configured SLA window"
    elif remaining_minutes <= request.warning_threshold_minutes:
        status = "AT_RISK"
        reason = "SLA is still open but inside the warning threshold"
    else:
        status = "ON_TRACK"
        reason = "SLA is inside the allowed operating window"
    return SlaEscalationResult(
        dispute_case_id=request.dispute_case_id,
        breach_detected=breach_detected,
        escalation_status=status,
        remaining_minutes=remaining_minutes,
        escalation_reason=reason,
        audit_event_type="sla_escalation_evaluated",
    )
