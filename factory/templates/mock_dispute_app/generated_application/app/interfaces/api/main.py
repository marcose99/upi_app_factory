from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
from generated_application.app.domain.exceptions import DomainError
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

from .error_handlers import domain_error_handler
from .schemas import CreateDisputeRequest, CreateDisputeResponse


app = FastAPI(title="Local UPI Dispute Resolution", version="0.29.0")
app.add_exception_handler(DomainError, domain_error_handler)


@app.post("/disputes", response_model=CreateDisputeResponse)
def create_dispute(
    request: CreateDisputeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> CreateDisputeResponse:
    service = DisputeService(SqliteUnitOfWork(Path("local_disputes.sqlite3")))
    dispute_id = service.create_dispute(
        CreateDisputeCommand(
            transaction_ref=request.transaction_ref,
            customer_upi=request.customer_upi,
            reason=request.reason,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
    )
    return CreateDisputeResponse(dispute_id=dispute_id)
