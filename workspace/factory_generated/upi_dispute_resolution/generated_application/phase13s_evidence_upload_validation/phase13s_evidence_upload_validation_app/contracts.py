from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EvidenceType = Literal[
    "customer_statement",
    "bank_statement",
    "upi_reference",
    "merchant_receipt",
]
UploaderType = Literal["customer", "operator", "bank_mock"]
ValidationStatus = Literal["ACCEPTED", "REJECTED"]


class EvidenceUploadRequest(BaseModel):
    """Local evidence metadata accepted by the generated dispute capability."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str = Field(min_length=3, max_length=64)
    transaction_id: str = Field(min_length=6, max_length=64)
    evidence_type: EvidenceType
    filename: str = Field(min_length=3, max_length=128)
    content_sha256: str = Field(min_length=64, max_length=64)
    content_size_bytes: int = Field(ge=1, le=5_000_000)
    uploaded_by: UploaderType
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("content_sha256")
    @classmethod
    def sha256_must_be_hex(cls, value: str) -> str:
        lowered = value.lower()
        if len(lowered) != 64:
            raise ValueError("content_sha256 must be exactly 64 hex characters")
        if any(character not in "0123456789abcdef" for character in lowered):
            raise ValueError("content_sha256 must contain only hex characters")
        return lowered


class EvidenceValidationResult(BaseModel):
    """Deterministic local validation result for uploaded evidence metadata."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    validation_status: ValidationStatus
    evidence_id: str
    dispute_case_id: str
    transaction_id: str
    risk_flags: list[str]
    audit_event_type: str
    audit_reference: str
