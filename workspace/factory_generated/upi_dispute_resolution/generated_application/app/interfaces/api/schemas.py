from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from generated_application.app.domain.entities import Dispute
from generated_application.app.security.pii_redaction import redact_upi


class CreateDisputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_ref: str = Field(min_length=8)
    customer_upi: str = Field(min_length=3)
    reason: str = Field(min_length=3)


class CreateDisputeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    certification_boundary: str = "certification_ready_not_certified"


class DisputeItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    transaction_ref: str
    masked_customer_upi: str
    reason: str
    owner_subject: str
    state: str
    version: int
    certification_boundary: str = "certification_ready_not_certified"

    @classmethod
    def from_domain(cls, dispute: Dispute) -> DisputeItemResponse:
        return cls(
            dispute_id=dispute.dispute_id.value,
            transaction_ref=dispute.transaction_ref.value,
            masked_customer_upi=redact_upi(dispute.customer_upi),
            reason=dispute.reason,
            owner_subject=dispute.owner_subject,
            state=dispute.state.value,
            version=dispute.version,
        )


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    correlation_id: str


class CreateFailedDebitCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_ref: str = Field(min_length=8)
    customer_upi: str = Field(min_length=3)
    amount: str = Field(min_length=1)
    reason_code: str = Field(min_length=3)


class AttachFailedDebitEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str = Field(min_length=3)
    source: str = Field(min_length=3)
    summary: str = Field(min_length=3)
    observed_at_utc: str = Field(min_length=20)
    expected_version: int | None = Field(default=None, ge=0)
    evidence_id: str | None = Field(default=None, min_length=4)


class RecordFailedDebitInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyst_notes: str = Field(min_length=3)
    simulated_bank_status: str = Field(min_length=3)
    expected_version: int | None = Field(default=None, ge=0)


class ProposeFailedDebitResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_kind: str = Field(default="compatibility_alias", min_length=3)
    reason_code: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    finalize_action: str = Field(default="propose_only", min_length=3)
    expected_version: int | None = Field(default=None, ge=0)


class ClassifyFailedDebitCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int | None = Field(default=None, ge=0)


class RequestFailedDebitHumanReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    expected_version: int | None = Field(default=None, ge=0)


class RecordFailedDebitReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern=r"^(APPROVED|REJECTED|MORE_EVIDENCE_REQUIRED)$")
    reason_code: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    approved_disposition: str | None = Field(default=None, min_length=3)
    review_id: str | None = Field(default=None, min_length=4)
    expected_version: int | None = Field(default=None, ge=0)


class RecordFailedDebitDispositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: str = Field(min_length=3)
    reason_code: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    expected_version: int | None = Field(default=None, ge=0)


class CloseFailedDebitCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    expected_version: int | None = Field(default=None, ge=0)


class QuarantineFailedDebitCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    expected_version: int | None = Field(default=None, ge=0)


class FailedDebitEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: str
    source: str
    summary: str
    observed_at_utc: str
    attached_by: str
    attached_at_utc: str
    content_sha256: str
    audit_link_hash: str


class FailedDebitEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    state: str
    aggregate_version: int
    actor_subject: str
    occurred_at_utc: str
    correlation_id: str
    payload: dict[str, Any]
    audit_link_hash: str


class FailedDebitCaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    transaction_ref: str
    masked_customer_upi: str
    amount: str
    currency: str
    reason_code: str
    case_type: str
    owner_subject: str
    assigned_analyst: str
    state: str
    version: int
    resolution_status: str
    classification: dict[str, Any] | None
    human_review_required: bool
    human_review_status: str
    pending_review_id: str | None
    proposed_disposition: str | None
    approved_disposition: str | None
    required_evidence_types: list[str]
    missing_evidence_types: list[str]
    evidence_count: int
    evidence: list[FailedDebitEvidenceResponse]
    latest_investigation: dict[str, Any] | None
    latest_resolution: dict[str, Any] | None
    latest_disposition: dict[str, Any] | None
    last_audit_integrity_status: str
    last_audit_integrity: dict[str, Any] | None
    closed_at_utc: str | None
    closed_by: str | None
    quarantined_at_utc: str | None
    quarantined_by: str | None
    quarantine_reason_code: str | None
    quarantine_reason: str | None
    created_at_utc: str
    updated_at_utc: str
    last_correlation_id: str
    audit_link_hash: str
    certification_boundary: str = "certification_ready_not_certified"

    @classmethod
    def from_detail(cls, detail: dict[str, Any]) -> FailedDebitCaseResponse:
        return cls.model_validate(
            {
                key: value
                for key, value in detail.items()
                if key not in {"timeline", "history", "review_history", "audit_integrity_checks"}
            }
        )


class FailedDebitCaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FailedDebitCaseResponse]
    limit: int
    cursor: int
    next_cursor: int | None
    filters: dict[str, Any]
    certification_boundary: str = "certification_ready_not_certified"


class FailedDebitTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    version: int
    state: str
    evidence: list[FailedDebitEvidenceResponse]
    timeline: list[FailedDebitEventResponse]
    review_history: list[dict[str, Any]]
    audit_integrity_checks: list[dict[str, Any]]
    audit_link_hash: str
    certification_boundary: str = "certification_ready_not_certified"


class FailedDebitAuditIntegrityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    version: int
    state: str
    passed: bool
    verification_status: str
    quarantine_applied: bool
    details: dict[str, Any]
    certification_boundary: str = "certification_ready_not_certified"
