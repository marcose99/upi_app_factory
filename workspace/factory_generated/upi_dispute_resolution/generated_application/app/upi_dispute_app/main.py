from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

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
from .runtime import (
    RuntimeState,
    build_runtime_state,
    configure_structured_logging,
    log_runtime_event,
    payload_fingerprint,
)
from .settings import RuntimeSettings
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
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    runtime_settings = settings or RuntimeSettings.from_env()
    runtime_state = build_runtime_state(runtime_settings)
    runtime_logger = configure_structured_logging(runtime_settings.log_level)
    repo = repository or DisputeRepository(runtime_settings.sqlite_path)
    audit = audit_logger or AuditLogger(runtime_settings.audit_log_path)
    gateway = ecosystem or MockEcosystemGateway()

    app = FastAPI(
        title="Generated UPI Dispute Resolution Application",
        version="0.39.0",
        description=BOUNDARY_NOTICE,
    )
    app.state.runtime = runtime_state
    app.state.runtime_logger = runtime_logger

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        runtime_state.counters.structured_errors += 1
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": exc.detail,
                    "path": request.url.path,
                    "boundary_notice": BOUNDARY_NOTICE,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        runtime_state.counters.validation_failures += 1
        runtime_state.counters.structured_errors += 1
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": jsonable_encoder(exc.errors()),
                    "path": request.url.path,
                    "boundary_notice": BOUNDARY_NOTICE,
                }
            },
        )

    async def get_repo() -> DisputeRepository:
        return repo

    async def get_audit() -> AuditLogger:
        return audit

    async def get_gateway() -> MockEcosystemGateway:
        return gateway

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app_id": "upi_dispute_resolution",
            "boundary": "local_app_with_mock_external_ecosystem",
            "runtime_hardening": runtime_state.report.as_dict(),
        }

    @app.get("/runtime/health")
    async def runtime_health() -> dict[str, object]:
        return {
            "status": runtime_state.report.status,
            "runtime_hardening": runtime_state.report.as_dict(),
        }

    @app.get("/runtime/metrics")
    async def runtime_metrics() -> dict[str, object]:
        return {
            "status": "available",
            "metrics": runtime_state.counters.as_dict(),
            "observability_scope": "local_structured_runtime_counters_only",
            "live_provider_calls_allowed": False,
        }

    @app.post(
        "/disputes",
        response_model=DisputeResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_dispute(
        payload: DisputeCreate,
        response: Response,
        current_repo: DisputeRepository = Depends(get_repo),
        current_audit: AuditLogger = Depends(get_audit),
    ) -> DisputeResponse:
        try:
            assert_no_obvious_real_sensitive_values(payload.description)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        record = build_dispute_record(payload)
        fingerprint = payload_fingerprint(payload)
        try:
            current_repo.add(record, request_fingerprint=fingerprint)
        except DuplicateClientRequestError as exc:
            stored_fingerprint = current_repo.get_request_fingerprint(payload.client_request_id)
            if stored_fingerprint == fingerprint:
                response.status_code = status.HTTP_200_OK
                runtime_state.counters.idempotency_replays += 1
                existing = current_repo.get_by_client_request_id(payload.client_request_id)
                return DisputeResponse(
                    dispute=existing,
                    next_actions=next_actions_for(existing),
                    boundary_notice=BOUNDARY_NOTICE,
                )
            raise HTTPException(
                status_code=409,
                detail="client_request_id already exists with a different payload",
            ) from exc

        runtime_state.counters.disputes_created += 1
        current_audit.record(
            event_type="dispute_created",
            actor="api",
            dispute_id=record.dispute_id,
            details={"dispute_type": record.dispute_type.value, "status": record.status.value},
        )
        log_runtime_event(
            runtime_logger,
            event_type="dispute_created",
            details={"dispute_id": record.dispute_id, "status": record.status.value},
        )
        return DisputeResponse(
            dispute=record,
            next_actions=next_actions_for(record),
            boundary_notice=BOUNDARY_NOTICE,
        )

    @app.get("/disputes", response_model=list[DisputeRecord])
    async def list_disputes(
        current_repo: DisputeRepository = Depends(get_repo),
    ) -> list[DisputeRecord]:
        return current_repo.list_all()

    @app.get("/disputes/{dispute_id}", response_model=DisputeResponse)
    async def get_dispute(
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
    async def run_mock_ecosystem_check(
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
        runtime_state.counters.mock_ecosystem_checks += 1
        log_runtime_event(
            runtime_logger,
            event_type="mock_ecosystem_check_completed",
            details={"dispute_id": dispute_id, "decision": decision.value},
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
