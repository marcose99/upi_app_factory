from __future__ import annotations

from pydantic import BaseModel, Field


class CreateDisputeRequest(BaseModel):
    transaction_ref: str = Field(min_length=8)
    customer_upi: str = Field(min_length=3)
    reason: str = Field(min_length=3)


class CreateDisputeResponse(BaseModel):
    dispute_id: str
    certification_boundary: str = "certification_ready_not_certified"


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    correlation_id: str
