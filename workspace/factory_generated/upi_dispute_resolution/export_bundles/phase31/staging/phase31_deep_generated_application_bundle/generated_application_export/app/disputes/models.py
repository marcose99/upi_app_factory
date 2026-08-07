from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


REQUIRED_EVIDENCE_LABELS = [
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]


class CaseStatus(str, Enum):
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CaseAction(str, Enum):
    ASSIGN_REVIEWER = "ASSIGN_REVIEWER"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    MARK_RESOLVED = "MARK_RESOLVED"
    CLOSE_CASE = "CLOSE_CASE"


class FailedTransactionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=6)
    customer_reference: str = Field(min_length=3)
    amount_paise: int = Field(gt=0)
    currency: str = "INR"
    failure_reason: str
    observed_at_utc: str
    evidence_labels: list[str] = Field(
        default_factory=lambda: REQUIRED_EVIDENCE_LABELS.copy()
    )


class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=6)
    created_by: str = Field(default="TECHNICAL_REVIEWER", min_length=3)


class CaseActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CaseAction
    reviewer: str = Field(default="TECHNICAL_REVIEWER", min_length=3)
    notes: str | None = None


class MockEvidenceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str
    boundary_type: str = "MOCK_BOUNDARY"
    data_label: str = "SYNTHETIC_DATA"
    observation: str
    observed_at_utc: str


class DisputeCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    transaction_id: str
    status: CaseStatus
    created_at_utc: str
    updated_at_utc: str
    created_by: str
    amount_paise: int
    currency: str
    customer_reference: str
    failure_reason: str
    evidence: list[MockEvidenceObservation]
    reviewer_notes: list[str]
    audit_event_ids: list[str]
    evidence_labels: list[str] = Field(
        default_factory=lambda: REQUIRED_EVIDENCE_LABELS.copy()
    )
