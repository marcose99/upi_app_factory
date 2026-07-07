from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["normal", "high", "regulatory"]
SlaStatus = Literal["WITHIN_SLA", "BREACHED", "ESCALATE_NOW"]


class SlaAssessmentRequest(BaseModel):
    """Local SLA assessment input generated from a requirement package."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str = Field(min_length=3, max_length=64)
    transaction_id: str = Field(min_length=6, max_length=64)
    received_at_utc: str = Field(min_length=20, max_length=40)
    now_utc: str = Field(min_length=20, max_length=40)
    sla_hours: int = Field(ge=1, le=336)
    priority: Priority = "normal"


class SlaAssessmentResult(BaseModel):
    """Deterministic local SLA assessment result."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str
    transaction_id: str
    elapsed_minutes: int
    remaining_minutes: int
    breached: bool
    escalation_required: bool
    sla_status: SlaStatus
    audit_event_type: str
    audit_reference: str
    risk_flags: list[str]
