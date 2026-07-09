from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DisputeType(str, Enum):
    FAILED_TRANSACTION = "failed_transaction"
    UNAUTHORIZED_TRANSACTION = "unauthorized_transaction"
    WRONG_CREDIT_OR_DEBIT = "wrong_credit_or_debit"
    DUPLICATE_DEBIT = "duplicate_debit"
    MERCHANT_NOT_PROVIDED_SERVICE = "merchant_not_provided_service"


class DisputeStatus(str, Enum):
    RECEIVED = "received"
    VALIDATION_PENDING = "validation_pending"
    EVIDENCE_PENDING = "evidence_pending"
    ECOSYSTEM_CHECK_PENDING = "ecosystem_check_pending"
    REFUND_INITIATED = "refund_initiated"
    CUSTOMER_ACTION_REQUIRED = "customer_action_required"
    ESCALATED_TO_ODR = "escalated_to_odr"
    REJECTED = "rejected"
    CLOSED = "closed"


class EcosystemDecision(str, Enum):
    REFUND_ELIGIBLE = "refund_eligible"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    ESCALATE_TO_ODR = "escalate_to_odr"
    REJECT = "reject"


class DisputeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_request_id: str = Field(min_length=8, max_length=80)
    dispute_type: DisputeType
    transaction_reference: str = Field(min_length=6, max_length=80)
    customer_upi_id: str = Field(min_length=5, max_length=120)
    amount_paise: int = Field(gt=0, le=20_000_000)
    description: str = Field(min_length=10, max_length=1000)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("client_request_id")
    @classmethod
    def validate_client_request_id(cls, value: str) -> str:
        allowed = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789"
            "-_"
        )
        if any(character not in allowed for character in value):
            raise ValueError("client_request_id must be alphanumeric with - or _ only")
        return value

    @field_validator("customer_upi_id")
    @classmethod
    def validate_upi_id_shape(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("customer_upi_id must contain @")
        return value

    @field_validator("transaction_reference")
    @classmethod
    def validate_transaction_reference(cls, value: str) -> str:
        allowed = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789"
            "-_"
        )
        if any(character not in allowed for character in value):
            raise ValueError(
                "transaction_reference must be alphanumeric with - or _ only"
            )
        return value

    @field_validator("evidence")
    @classmethod
    def validate_evidence_boundary(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 10:
            raise ValueError("evidence can include at most 10 fields")
        encoded_length = len(str(value))
        if encoded_length > 4000:
            raise ValueError("evidence payload is too large for the local runtime")
        for key in value:
            if not isinstance(key, str) or len(key) > 80:
                raise ValueError("evidence keys must be strings up to 80 characters")
        return value


class DisputeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    client_request_id: str
    dispute_type: DisputeType
    transaction_reference: str
    masked_customer_upi_id: str
    amount_paise: int
    description: str
    evidence: dict[str, Any]
    status: DisputeStatus
    created_at_utc: str
    updated_at_utc: str
    domain_notes: list[str] = Field(default_factory=list)


class DisputeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute: DisputeRecord
    next_actions: list[str]
    boundary_notice: str


class EcosystemCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_id: str
    decision: EcosystemDecision
    new_status: DisputeStatus
    reason: str
    mock_sources_checked: list[str]


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    dispute_id: str | None = None
    actor: str
    details: dict[str, Any]
    created_at_utc: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"
