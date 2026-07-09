from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .audit import AuditLogger
from .cqrs import GetDisputeQuery, ListDisputesQuery, RunMockEcosystemCheckCommand
from .cqrs import SubmitDisputeCommand
from .domain_events import (
    DomainEventCollector,
    dispute_created_event,
    mock_ecosystem_checked_event,
)
from .errors import AppErrorCode, ApplicationError
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
from .repository import DuplicateBusinessSubmissionError
from .repository import DuplicateClientRequestError
from .runtime import (
    RuntimeState,
    build_runtime_state,
    configure_structured_logging,
    log_runtime_event,
    payload_fingerprint,
)
from .settings import RuntimeSettings
from .unit_of_work import LocalSqliteUnitOfWork
from .workflow import BOUNDARY_NOTICE, initial_status, next_actions_for
from .workflow import status_from_ecosystem_decision


def build_dispute_record(command: SubmitDisputeCommand) -> DisputeRecord:
    now = utc_now_iso()
    return DisputeRecord(
        dispute_id=new_id("disp"),
        client_request_id=command.client_request_id,
        dispute_type=command.dispute_type,
        transaction_reference=command.transaction_reference,
        masked_customer_upi_id=mask_upi_id(command.customer_upi_id),
        amount_paise=command.amount_paise,
        description=command.description,
        evidence=command.evidence,
        status=initial_status(command.dispute_type),
        created_at_utc=now,
        updated_at_utc=now,
        domain_notes=["Initial local dispute simulation record created."],
    )


def business_duplicate_fingerprint(command: SubmitDisputeCommand) -> str:
    return payload_fingerprint(
        {
            "dispute_type": command.dispute_type.value,
            "transaction_reference": command.transaction_reference,
            "customer_upi_id": command.customer_upi_id,
            "amount_paise": command.amount_paise,
            "description": command.description,
            "evidence": command.evidence,
        }
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
    unit_of_work = LocalSqliteUnitOfWork(repo)
    domain_events = DomainEventCollector()
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

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        runtime_state.counters.structured_errors += 1
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.as_error_payload(
                path=request.url.path,
                boundary_notice=BOUNDARY_NOTICE,
            ),
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
        command = SubmitDisputeCommand.from_payload(payload)
        try:
            assert_no_obvious_real_sensitive_values(command.description)
        except ValueError as exc:
            raise ApplicationError(
                AppErrorCode.VALIDATION_BOUNDARY,
                str(exc),
                http_status=422,
            ) from exc

        record = build_dispute_record(command)
        fingerprint = payload_fingerprint(command)
        business_fingerprint = business_duplicate_fingerprint(command)
        try:
            current_repo.add(
                record,
                request_fingerprint=fingerprint,
                business_fingerprint=business_fingerprint,
            )
            unit_of_work.commit()
        except DuplicateClientRequestError as exc:
            stored_fingerprint = current_repo.get_request_fingerprint(command.client_request_id)
            if stored_fingerprint == fingerprint:
                existing = current_repo.get_by_client_request_id(command.client_request_id)
                runtime_state.counters.idempotency_replays += 1
                response.status_code = status.HTTP_200_OK
                log_runtime_event(
                    runtime_logger,
                    event_type="idempotency_replay",
                    details={
                        "dispute_id": existing.dispute_id,
                        "client_request_id": existing.client_request_id,
                    },
                )
                return DisputeResponse(
                    dispute=existing,
                    next_actions=next_actions_for(existing),
                    boundary_notice=BOUNDARY_NOTICE,
                )
            raise ApplicationError(
                AppErrorCode.PAYLOAD_CONFLICT,
                "client_request_id already exists with a different payload",
                http_status=409,
            ) from exc
        except DuplicateBusinessSubmissionError as exc:
            raise ApplicationError(
                AppErrorCode.PAYLOAD_CONFLICT,
                "duplicate business dispute submission already exists",
                http_status=409,
            ) from exc

        runtime_state.counters.disputes_created += 1
        domain_events.record(dispute_created_event(record))
        emitted_events = [event.as_dict() for event in domain_events.drain()]
        current_audit.record(
            event_type="dispute_created",
            actor="api",
            dispute_id=record.dispute_id,
            details={
                "dispute_type": record.dispute_type.value,
                "status": record.status.value,
                "domain_events": emitted_events,
            },
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
        ListDisputesQuery()
        return current_repo.list_all()

    @app.get("/disputes/{dispute_id}", response_model=DisputeResponse)
    async def get_dispute(
        dispute_id: str,
        current_repo: DisputeRepository = Depends(get_repo),
    ) -> DisputeResponse:
        query = GetDisputeQuery(dispute_id=dispute_id)
        try:
            record = current_repo.get(query.dispute_id)
        except DisputeNotFoundError as exc:
            raise exc
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
        command = RunMockEcosystemCheckCommand(dispute_id=dispute_id)
        try:
            record = current_repo.get(command.dispute_id)
        except DisputeNotFoundError as exc:
            raise exc

        decision, reason, sources = current_gateway.decide(record)
        new_status = status_from_ecosystem_decision(decision)
        updated = current_repo.update_status(
            dispute_id=command.dispute_id,
            status=new_status,
            updated_at_utc=utc_now_iso(),
            note=reason,
        )
        unit_of_work.commit()
        domain_events.record(
            mock_ecosystem_checked_event(
                updated,
                decision=decision.value,
                sources=sources,
            )
        )
        emitted_events = [event.as_dict() for event in domain_events.drain()]
        current_audit.record(
            event_type="mock_ecosystem_check_completed",
            actor="mock_ecosystem",
            dispute_id=command.dispute_id,
            details={
                "decision": decision.value,
                "new_status": updated.status.value,
                "sources": sources,
                "domain_events": emitted_events,
            },
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
