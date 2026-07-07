from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EscalationStatus = Literal["ON_TRACK", "AT_RISK", "BREACHED"]


class SlaEscalationRequest(BaseModel):
    """Local SLA escalation input for a generated dispute capability."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str = Field(min_length=3, max_length=64)
    elapsed_minutes: int = Field(ge=0, le=30 * 24 * 60)
    sla_minutes: int = Field(ge=1, le=30 * 24 * 60)
    warning_threshold_minutes: int = Field(default=30, ge=0, le=24 * 60)


class SlaEscalationResult(BaseModel):
    """Deterministic local SLA escalation output."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str
    breach_detected: bool
    escalation_status: EscalationStatus
    remaining_minutes: int
    escalation_reason: str
    audit_event_type: str
