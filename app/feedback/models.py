from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class FeedbackSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    OBSERVATION = "OBSERVATION"
    PRAISE = "PRAISE"


class FeedbackStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    TRIAGED = "TRIAGED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CONVERTED_TO_TASK = "CONVERTED_TO_TASK"
    RESOLVED = "RESOLVED"
    VALIDATED = "VALIDATED"
    CLOSED = "CLOSED"
    RISK_ACCEPTED = "RISK_ACCEPTED"


class HumanFeedbackCreate(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3)
    reviewer_role: str = Field(default="TECHNICAL_REVIEWER")
    artifact_path: str | None = None
    agent_id: str | None = None
    severity: FeedbackSeverity = FeedbackSeverity.OBSERVATION
    quality_dimensions: list[str] = Field(default_factory=list)


class HumanFeedback(BaseModel):
    feedback_id: str
    created_at_utc: str
    status: FeedbackStatus
    title: str
    description: str
    reviewer_role: str
    artifact_path: str | None
    agent_id: str | None
    severity: FeedbackSeverity
    quality_dimensions: list[str]
    audit_event_ids: list[str]


def new_feedback_id() -> str:
    return f"FB-{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
