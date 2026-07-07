from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .contracts import SlaAssessmentRequest, SlaAssessmentResult


def _parse_utc_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stable_reference(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16].upper()


def assess_sla_status(request: SlaAssessmentRequest) -> SlaAssessmentResult:
    """Assess SLA status locally without calling external systems."""

    received_at = _parse_utc_timestamp(request.received_at_utc)
    now_at = _parse_utc_timestamp(request.now_utc)
    elapsed_minutes = int((now_at - received_at).total_seconds() // 60)
    allowed_minutes = request.sla_hours * 60
    remaining_minutes = max(allowed_minutes - elapsed_minutes, 0)
    breached = elapsed_minutes > allowed_minutes
    escalation_required = breached and request.priority in {"high", "regulatory"}
    risk_flags: list[str] = []
    if elapsed_minutes < 0:
        risk_flags.append("NEGATIVE_ELAPSED_TIME")
    if breached:
        risk_flags.append("SLA_BREACHED")
    if escalation_required:
        risk_flags.append("ESCALATION_REQUIRED")
    if request.priority == "regulatory" and breached:
        status = "ESCALATE_NOW"
    elif breached:
        status = "BREACHED"
    else:
        status = "WITHIN_SLA"
    reference = _stable_reference(
        request.dispute_case_id,
        request.transaction_id,
        request.received_at_utc,
        request.now_utc,
        str(request.sla_hours),
        request.priority,
    )
    return SlaAssessmentResult(
        dispute_case_id=request.dispute_case_id,
        transaction_id=request.transaction_id,
        elapsed_minutes=elapsed_minutes,
        remaining_minutes=remaining_minutes,
        breached=breached,
        escalation_required=escalation_required,
        sla_status=status,
        audit_event_type="sla_status_assessed",
        audit_reference=f"AUD-SLA-{reference}",
        risk_flags=risk_flags,
    )
