from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status

from .audit import AuditLogger
from .mock_ecosystem import MockEcosystemGateway
from .models import (
    DisputeCreate,
    DisputeRecord,
    DisputeResponse,
    EcosystemCheckResult,
    new_id,
    utc_now_iso,
)
from .pii import assert_no_obvious_real_sensitive_values, mask_upi_id
from .repository import DisputeNotFoundError, DisputeRepository
from .repository import DuplicateClientRequestError
from .workflow import BOUNDARY_NOTICE, initial_status, next_actions_for
from .workflow import status_from_ecosystem_decision


def build_dispute_record(payload: DisputeCreate) -> DisputeRecord:
    now = utc_now_iso()
    return DisputeRecord(
        dispute_id=new_id("disp"),
        client_request_id=payload.client_request_id,
        dispute_type=payload.dispute_type,
        transaction_reference=payload.transaction_reference,
        masked_customer_upi_id=mask_upi_id(payload.customer_upi_id),
        amount_paise=payload.amount_paise,
        description=payload.description,
        evidence=payload.evidence,
        status=initial_status(payload.dispute_type),
        created_at_utc=now,
        updated_at_utc=now,
        domain_notes=["Initial local dispute simulation record created."],
    )


def create_app(
    *,
    repository: DisputeRepository | None = None,
    audit_logger: AuditLogger | None = None,
    ecosystem: MockEcosystemGateway | None = None,
) -> FastAPI:
    repo = repository or DisputeRepository()
    audit = audit_logger or AuditLogger(Path("evidence/audit_events.jsonl"))
    gateway = ecosystem or MockEcosystemGateway()

    app = FastAPI(
        title="Generated UPI Dispute Resolution Application",
        version="0.13.1",
        description=BOUNDARY_NOTICE,
    )

    def get_repo() -> DisputeRepository:
        return repo

    def get_audit() -> AuditLogger:
        return audit

    def get_gateway() -> MockEcosystemGateway:
        return gateway

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app_id": "upi_dispute_resolution",
            "boundary": "local_app_with_mock_external_ecosystem",
        }

    @app.post(
        "/disputes",
        response_model=DisputeResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_dispute(
        payload: DisputeCreate,
        current_repo: DisputeRepository = Depends(get_repo),
        current_audit: AuditLogger = Depends(get_audit),
    ) -> DisputeResponse:
        try:
            assert_no_obvious_real_sensitive_values(payload.description)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        record = build_dispute_record(payload)
        try:
            current_repo.add(record)
        except DuplicateClientRequestError as exc:
            raise HTTPException(status_code=409, detail="client_request_id already exists") from exc

        current_audit.record(
            event_type="dispute_created",
            actor="api",
            dispute_id=record.dispute_id,
            details={"dispute_type": record.dispute_type.value, "status": record.status.value},
        )
        return DisputeResponse(
            dispute=record,
            next_actions=next_actions_for(record),
            boundary_notice=BOUNDARY_NOTICE,
        )

    @app.get("/disputes", response_model=list[DisputeRecord])
    def list_disputes(
        current_repo: DisputeRepository = Depends(get_repo),
    ) -> list[DisputeRecord]:
        return current_repo.list_all()

    @app.get("/disputes/{dispute_id}", response_model=DisputeResponse)
    def get_dispute(
        dispute_id: str,
        current_repo: DisputeRepository = Depends(get_repo),
    ) -> DisputeResponse:
        try:
            record = current_repo.get(dispute_id)
        except DisputeNotFoundError as exc:
            raise HTTPException(status_code=404, detail="dispute not found") from exc
        return DisputeResponse(
            dispute=record,
            next_actions=next_actions_for(record),
            boundary_notice=BOUNDARY_NOTICE,
        )

    @app.post(
        "/disputes/{dispute_id}/actions/mock-ecosystem-check",
        response_model=EcosystemCheckResult,
    )
    def run_mock_ecosystem_check(
        dispute_id: str,
        current_repo: DisputeRepository = Depends(get_repo),
        current_audit: AuditLogger = Depends(get_audit),
        current_gateway: MockEcosystemGateway = Depends(get_gateway),
    ) -> EcosystemCheckResult:
        try:
            record = current_repo.get(dispute_id)
        except DisputeNotFoundError as exc:
            raise HTTPException(status_code=404, detail="dispute not found") from exc

        decision, reason, sources = current_gateway.decide(record)
        new_status = status_from_ecosystem_decision(decision)
        updated = current_repo.update_status(
            dispute_id=dispute_id,
            status=new_status,
            updated_at_utc=utc_now_iso(),
            note=reason,
        )
        current_audit.record(
            event_type="mock_ecosystem_check_completed",
            actor="mock_ecosystem",
            dispute_id=dispute_id,
            details={"decision": decision.value, "new_status": updated.status.value, "sources": sources},
        )
        return EcosystemCheckResult(
            dispute_id=dispute_id,
            decision=decision,
            new_status=updated.status,
            reason=reason,
            mock_sources_checked=sources,
        )

    return app


app = create_app()
