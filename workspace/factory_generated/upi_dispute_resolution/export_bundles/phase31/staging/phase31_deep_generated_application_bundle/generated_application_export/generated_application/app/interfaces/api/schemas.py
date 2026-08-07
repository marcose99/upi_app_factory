from __future__ import annotations

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
