from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateDisputeCommand:
    transaction_ref: str
    customer_upi: str
    reason: str
    idempotency_key: str
    correlation_id: str
    owner_subject: str = "local-system"
    owner_role: str = "system"


@dataclass(frozen=True)
class CreateFailedDebitCaseCommand:
    transaction_ref: str
    customer_upi: str
    amount: str
    reason_code: str
    idempotency_key: str
    correlation_id: str
    owner_subject: str = "local-system"
    owner_role: str = "system"


@dataclass(frozen=True)
class AttachFailedDebitEvidenceCommand:
    dispute_id: str
    evidence_type: str
    source: str
    summary: str
    observed_at_utc: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None
    evidence_id: str | None = None


@dataclass(frozen=True)
class RecordInvestigationOutcomeCommand:
    dispute_id: str
    analyst_notes: str
    simulated_bank_status: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None


@dataclass(frozen=True)
class ClassifyFailedDebitCaseCommand:
    dispute_id: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None


@dataclass(frozen=True)
class RequestFailedDebitHumanReviewCommand:
    dispute_id: str
    reason_code: str
    rationale: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None


@dataclass(frozen=True)
class RecordFailedDebitReviewDecisionCommand:
    dispute_id: str
    decision: str
    reason_code: str
    rationale: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    approved_disposition: str | None = None
    review_id: str | None = None
    expected_version: int | None = None


@dataclass(frozen=True)
class RecordFailedDebitDispositionCommand:
    dispute_id: str
    disposition: str
    reason_code: str
    rationale: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None


@dataclass(frozen=True)
class CloseFailedDebitCaseCommand:
    dispute_id: str
    reason_code: str
    rationale: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None


@dataclass(frozen=True)
class QuarantineFailedDebitCaseCommand:
    dispute_id: str
    reason_code: str
    rationale: str
    idempotency_key: str
    correlation_id: str
    actor_subject: str
    actor_role: str
    expected_version: int | None = None
