from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from generated_application.app.application.commands import (
    AttachFailedDebitEvidenceCommand,
    ClassifyFailedDebitCaseCommand,
    CloseFailedDebitCaseCommand,
    CreateFailedDebitCaseCommand,
    QuarantineFailedDebitCaseCommand,
    RecordFailedDebitDispositionCommand,
    RecordFailedDebitReviewDecisionCommand,
    RecordInvestigationOutcomeCommand,
    RequestFailedDebitHumanReviewCommand,
)
from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService, FailedDebitRuntimeService
from generated_application.app.domain.exceptions import DomainError
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import (
    SqliteUnitOfWork,
)
from generated_application.app.observability.logging import log_event
from generated_application.app.observability.metrics import METRICS, route_label
from generated_application.app.observability.tracing import (
    current_traceparent,
    trace_context_from_headers,
    use_trace_context,
)
from generated_application.app.runtime import RuntimeLifecycle
from generated_application.app.security.identity import (
    LocalAuthorizationPolicy,
    Principal,
    local_principal,
    openapi_security_schemes,
)

from .error_handlers import (
    domain_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from .schemas import CreateDisputeRequest, CreateDisputeResponse, DisputeItemResponse
from .schemas import (
    AttachFailedDebitEvidenceRequest,
    ClassifyFailedDebitCaseRequest,
    CloseFailedDebitCaseRequest,
    CreateFailedDebitCaseRequest,
    FailedDebitAuditIntegrityResponse,
    FailedDebitCaseListResponse,
    FailedDebitCaseResponse,
    FailedDebitTimelineResponse,
    ProposeFailedDebitResolutionRequest,
    QuarantineFailedDebitCaseRequest,
    RecordFailedDebitDispositionRequest,
    RecordFailedDebitReviewDecisionRequest,
    RecordFailedDebitInvestigationRequest,
    RequestFailedDebitHumanReviewRequest,
)


DATABASE_PATH = Path(os.environ.get("UPI_DISPUTE_SQLITE_PATH", "state/local_disputes.sqlite3"))
LOGGER = logging.getLogger("generated_application.runtime")
RUNTIME = RuntimeLifecycle(DATABASE_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    RUNTIME.startup()
    log_event(LOGGER, "runtime.startup", RUNTIME.startup_status()[1])
    try:
        yield
    finally:
        RUNTIME.shutdown()
        log_event(LOGGER, "runtime.shutdown", {"status": "shutdown_complete"})


app = FastAPI(
    title="Local UPI Dispute Resolution",
    version="0.40.0",
    openapi_version="3.1.0",
    lifespan=lifespan,
)
app.state.database_path = DATABASE_PATH


async def _domain_exception_adapter(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    return await domain_error_handler(request, exc)


async def _http_exception_adapter(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    return await http_exception_handler(request, exc)


async def _validation_exception_adapter(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return await validation_error_handler(request, exc)


app.add_exception_handler(DomainError, _domain_exception_adapter)
app.add_exception_handler(HTTPException, _http_exception_adapter)
app.add_exception_handler(RequestValidationError, _validation_exception_adapter)


class RuntimeObservabilityMiddleware:
    def __init__(self, wrapped_app: ASGIApp) -> None:
        self.wrapped_app = wrapped_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.wrapped_app(scope, receive, send)
            return

        started = perf_counter()
        request = Request(scope, receive=receive)
        correlation_id = request.headers.get("x-correlation-id", "local")
        context = trace_context_from_headers(
            traceparent=request.headers.get("traceparent"),
            tracestate=request.headers.get("tracestate"),
            correlation_id=correlation_id,
        )
        status_code = 500

        async def send_with_observability(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = MutableHeaders(scope=message)
                headers["traceparent"] = current_traceparent()
                headers["x-correlation-id"] = correlation_id
                headers["x-content-type-options"] = "nosniff"
                headers["referrer-policy"] = "no-referrer"
                headers["cache-control"] = "no-store"
                headers["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
            await send(message)

        with use_trace_context(context):
            if RUNTIME.draining and request.url.path not in {
                "/live",
                "/startup",
                "/metrics",
                "/runtime/diagnostics",
            }:
                outcome = "draining"
                response: Response = JSONResponse(
                    status_code=503,
                    content={"status": "draining", "correlation_id": correlation_id},
                )
                await response(scope, receive, send_with_observability)
            else:
                try:
                    await self.wrapped_app(scope, receive, send_with_observability)
                    outcome = "success" if status_code < 500 else "error"
                except Exception:
                    METRICS.record_http(
                        method=request.method,
                        route=route_label(request.url.path),
                        outcome="error",
                        duration_seconds=perf_counter() - started,
                    )
                    log_event(
                        LOGGER,
                        "http.request.failed",
                        {
                            "method": request.method,
                            "route": route_label(request.url.path),
                            "outcome": "error",
                        },
                    )
                    raise

        METRICS.record_http(
            method=request.method,
            route=route_label(request.url.path),
            outcome=outcome,
            duration_seconds=perf_counter() - started,
        )
        log_event(
            LOGGER,
            "http.request.completed",
            {
                "method": request.method,
                "route": route_label(request.url.path),
                "status_code": status_code,
                "outcome": outcome,
            },
        )


app.add_middleware(RuntimeObservabilityMiddleware)


def _install_openapi_contract() -> None:
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, object]:
        schema = original_openapi()
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes.update(openapi_security_schemes())
        schema["x-compatibility"] = {
            "openapi_minimum": "3.1.0",
            "problem_details": "RFC 9457 compatible",
            "oauth2_security_profile_benchmark": "RFC 9700 aligned; no certification claim",
            "live_provider_calls_allowed": False,
        }
        paths = schema.get("paths", {})
        if isinstance(paths, dict):
            _secure_operation(
                paths,
                "/disputes",
                "post",
                operation_id="createDispute",
                scopes=("dispute:create",),
                summary="Create a local simulated dispute",
            )
            _secure_operation(
                paths,
                "/disputes",
                "get",
                operation_id="listDisputes",
                scopes=("dispute:read:any",),
                summary="List local simulated disputes",
            )
            _secure_operation(
                paths,
                "/disputes/{dispute_id}",
                "get",
                operation_id="getDispute",
                scopes=("dispute:read",),
                summary="Get one local simulated dispute",
            )
            _secure_operation(
                paths,
                "/v1/disputes",
                "post",
                operation_id="createFailedDebitCase",
                scopes=("dispute:create",),
                summary="Create a versioned failed-debit dispute case",
            )
            _secure_operation(
                paths,
                "/v1/disputes",
                "get",
                operation_id="listFailedDebitCases",
                scopes=("dispute:read:any",),
                summary="List versioned failed-debit dispute cases",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}",
                "get",
                operation_id="getFailedDebitCase",
                scopes=("dispute:read",),
                summary="Get one versioned failed-debit dispute case",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/evidence",
                "post",
                operation_id="attachFailedDebitEvidence",
                scopes=("dispute:evidence:write",),
                summary="Attach required failed-debit evidence",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/investigate",
                "post",
                operation_id="recordFailedDebitInvestigation",
                scopes=("dispute:investigation:write",),
                summary="Record a deterministic local investigation outcome",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/classify",
                "post",
                operation_id="classifyFailedDebitCase",
                scopes=("dispute:classify:write",),
                summary="Classify a deterministic local failed-debit case",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/human-review",
                "post",
                operation_id="requestFailedDebitHumanReview",
                scopes=("dispute:review:write",),
                summary="Request explicit human review for a failed-debit case",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/review-decisions",
                "post",
                operation_id="recordFailedDebitReviewDecision",
                scopes=("dispute:review:write",),
                summary="Record a governed failed-debit human-review decision",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/disposition",
                "post",
                operation_id="recordFailedDebitDisposition",
                scopes=("dispute:disposition:write",),
                summary="Record a governed failed-debit disposition",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/close",
                "post",
                operation_id="closeFailedDebitCase",
                scopes=("dispute:close:write",),
                summary="Close a governed failed-debit case after audit verification",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/quarantine",
                "post",
                operation_id="quarantineFailedDebitCase",
                scopes=("dispute:quarantine:write",),
                summary="Quarantine a failed-debit case on policy or integrity failure",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/history",
                "get",
                operation_id="getFailedDebitHistory",
                scopes=("dispute:history:read",),
                summary="Read failed-debit case history, review lineage and evidence",
            )
            _secure_operation(
                paths,
                "/v1/disputes/{dispute_id}/audit-integrity",
                "get",
                operation_id="verifyFailedDebitAuditIntegrity",
                scopes=("dispute:audit:read",),
                summary="Verify failed-debit audit-chain integrity",
            )
            _secure_operation(
                paths,
                "/drain",
                "post",
                operation_id="beginDrain",
                scopes=("runtime:drain",),
                summary="Put the local runtime into draining mode",
            )
            _secure_operation(
                paths,
                "/runtime/diagnostics",
                "get",
                operation_id="runtimeDiagnostics",
                scopes=("runtime:diagnostics",),
                summary="Read bounded local runtime diagnostics",
            )
        return schema

    setattr(app, "openapi", custom_openapi)


def _secure_operation(
    paths: dict[str, object],
    path: str,
    method: str,
    *,
    operation_id: str,
    scopes: tuple[str, ...],
    summary: str,
) -> None:
    route = paths.get(path)
    if not isinstance(route, dict):
        return
    operation = route.get(method)
    if not isinstance(operation, dict):
        return
    operation["operationId"] = operation_id
    operation["summary"] = summary
    operation["security"] = [
        {"LocalTestPrincipal": []},
        {"OAuth2AuthorizationCodePkce": list(scopes)},
    ]
    operation["x-local-boundary"] = {
        "live_provider_calls_allowed": False,
        "auth_profile": "signed local bearer token; header fallback requires explicit test env",
        "response_alias": "masked_customer_upi",
    }
    operation["x-deterministic-examples"] = {
        "authorization": "Authorization: Bearer <deterministic-local-hmac-test-token>",
        "required_scopes": list(scopes),
        "live_provider_calls_allowed": False,
    }


_install_openapi_contract()


def _failed_debit_service() -> FailedDebitRuntimeService:
    app.state.database_path = DATABASE_PATH
    return FailedDebitRuntimeService(SqliteUnitOfWork(DATABASE_PATH))


class EchoScenarioRequest(BaseModel):
    client_request_id: str = Field(min_length=1, max_length=128)
    amount: int = Field(ge=0)


async def local_principal_dependency(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    subject: str | None = Header(default=None, alias="X-Local-Subject"),
    roles: str = Header(default="", alias="X-Local-Roles"),
    scopes: str = Header(default="", alias="X-Local-Scopes"),
) -> Principal:
    principal = local_principal(
        authorization=authorization,
        subject=subject,
        roles=roles,
        scopes=scopes,
    )
    request.state.principal = principal
    return principal


@app.get("/startup")
async def startup_probe() -> JSONResponse:
    status_code, payload = RUNTIME.startup_status()
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/live")
async def liveness_probe() -> JSONResponse:
    status_code, payload = RUNTIME.liveness()
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/ready")
async def readiness_probe() -> JSONResponse:
    status_code, payload = RUNTIME.readiness()
    return JSONResponse(status_code=status_code, content=payload)


@app.post("/drain")
async def drain(principal: Principal = Depends(local_principal_dependency)) -> dict[str, object]:
    LocalAuthorizationPolicy().require(principal, scopes=("runtime:drain",))
    return cast(dict[str, object], RUNTIME.begin_drain())


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "startup": RUNTIME.started, "live": RUNTIME.live}


@app.get("/runtime/health")
async def runtime_health() -> dict[str, str]:
    return {"status": "passed", "mode": "mock-safe-local"}


@app.get("/capabilities")
async def capabilities() -> dict[str, object]:
    return {
        "mock_only": True,
        "capabilities": [
            "failed_debit_disputes",
            "evidence_collection",
            "investigation",
            "human_review",
            "disposition",
            "audit_integrity",
            "closure",
            "health",
            "echo",
            "ready",
        ],
        "live_provider_calls_allowed": False,
        "default_runtime_llm_calls": 0,
    }


@app.post("/scenario/echo", response_model=None)
async def scenario_echo(request: Request) -> JSONResponse:
    payload = await request.json()
    try:
        scenario = EchoScenarioRequest.model_validate(payload)
    except ValidationError:
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error"}})
    return JSONResponse(
        status_code=200,
        content={
            "accepted": True,
            "client_request_id": scenario.client_request_id,
            "amount": scenario.amount,
            "replay_status": 200,
        },
    )


@app.get("/missing")
async def missing() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": {"code": "not_found"}})


@app.get("/runtime/diagnostics")
async def runtime_diagnostics(principal: Principal = Depends(local_principal_dependency)) -> dict[str, object]:
    LocalAuthorizationPolicy().require(principal, scopes=("runtime:diagnostics",))
    return cast(dict[str, object], RUNTIME.diagnostics())


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        METRICS.openmetrics(),
        media_type="application/openmetrics-text; version=1.0.0; charset=utf-8",
    )


@app.post("/disputes", response_model=CreateDisputeResponse, status_code=201)
async def create_dispute(
    request: CreateDisputeRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> CreateDisputeResponse:
    LocalAuthorizationPolicy().require(principal, scopes=("dispute:create",))
    app.state.database_path = DATABASE_PATH
    service = DisputeService(SqliteUnitOfWork(DATABASE_PATH))
    dispute_id = service.create_dispute(
        CreateDisputeCommand(
            transaction_ref=request.transaction_ref,
            customer_upi=request.customer_upi,
            reason=request.reason,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            owner_subject=principal.subject,
            owner_role=principal.primary_role,
        )
    )
    METRICS.record_business_event(event_type="dispute.created", outcome="success")
    return CreateDisputeResponse(dispute_id=dispute_id)


@app.get("/disputes")
async def list_disputes(
    limit: int = Query(default=25, ge=1),
    cursor: int = Query(default=0, ge=0),
    principal: Principal = Depends(local_principal_dependency),
) -> dict[str, object]:
    LocalAuthorizationPolicy().require(principal, scopes=("dispute:read:any",))
    if limit > 100:
        raise HTTPException(status_code=429, detail="maximum page size exceeded")
    app.state.database_path = DATABASE_PATH
    service = DisputeService(SqliteUnitOfWork(DATABASE_PATH))
    disputes = service.list_disputes(limit=limit, cursor=cursor)
    return {
        "items": [DisputeItemResponse.from_domain(dispute).model_dump() for dispute in disputes],
        "limit": limit,
        "cursor": cursor,
        "next_cursor": cursor + len(disputes) if len(disputes) == limit else None,
        "max_page_size": 100,
    }


@app.get("/disputes/{dispute_id}", response_model=DisputeItemResponse)
async def get_dispute(
    dispute_id: str,
    principal: Principal = Depends(local_principal_dependency),
) -> DisputeItemResponse:
    LocalAuthorizationPolicy().require(principal, scopes=("dispute:read",))
    app.state.database_path = DATABASE_PATH
    service = DisputeService(SqliteUnitOfWork(DATABASE_PATH))
    dispute = service.get_dispute(dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="dispute not found")
    LocalAuthorizationPolicy().require_object_access(
        principal,
        owner_subject=dispute.owner_subject,
        scope="dispute:read",
    )
    return DisputeItemResponse.from_domain(dispute)


@app.post("/v1/disputes", response_model=FailedDebitCaseResponse, status_code=201)
async def create_failed_debit_case(
    request: CreateFailedDebitCaseRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:create",))
    policy.require_role(principal, roles=("payer", "customer_support_agent"))
    detail = _failed_debit_service().create_case(
        CreateFailedDebitCaseCommand(
            transaction_ref=request.transaction_ref,
            customer_upi=request.customer_upi,
            amount=request.amount,
            reason_code=request.reason_code,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            owner_subject=principal.subject,
            owner_role=principal.primary_role,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.case_created", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.get("/v1/disputes", response_model=FailedDebitCaseListResponse)
async def list_failed_debit_cases(
    limit: int = Query(default=25, ge=1),
    cursor: int = Query(default=0, ge=0),
    transaction_reference: str | None = Query(default=None),
    state: str | None = Query(default=None),
    age_bucket: str | None = Query(default=None),
    analyst: str | None = Query(default=None),
    resolution_status: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    human_review_status: str | None = Query(default=None),
    principal: Principal = Depends(local_principal_dependency),
) -> FailedDebitCaseListResponse:
    LocalAuthorizationPolicy().require(principal, scopes=("dispute:read:any",))
    if limit > 100:
        raise HTTPException(status_code=429, detail="maximum page size exceeded")
    payload = _failed_debit_service().list_cases(
        limit=limit,
        cursor=cursor,
        transaction_reference=transaction_reference,
        state=state,
        age_bucket=age_bucket,
        analyst=analyst,
        resolution_status=resolution_status,
        classification=classification,
        human_review_status=human_review_status,
    )
    items = [
        FailedDebitCaseResponse.from_detail(item).model_dump()
        for item in payload["items"]
    ]
    return FailedDebitCaseListResponse.model_validate({**payload, "items": items})


@app.get("/v1/disputes/{dispute_id}", response_model=FailedDebitCaseResponse)
async def get_failed_debit_case(
    dispute_id: str,
    principal: Principal = Depends(local_principal_dependency),
) -> FailedDebitCaseResponse:
    LocalAuthorizationPolicy().require(principal, scopes=("dispute:read",))
    detail = _failed_debit_service().get_case(dispute_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    LocalAuthorizationPolicy().require_object_access(
        principal,
        owner_subject=str(detail["owner_subject"]),
        scope="dispute:read",
    )
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/evidence", response_model=FailedDebitCaseResponse)
async def attach_failed_debit_evidence(
    dispute_id: str,
    request: AttachFailedDebitEvidenceRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:evidence:write",))
    policy.require_role(principal, roles=("customer_support_agent", "dispute_operations_analyst"))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().attach_evidence(
        AttachFailedDebitEvidenceCommand(
            dispute_id=dispute_id,
            evidence_type=request.evidence_type,
            source=request.source,
            summary=request.summary,
            observed_at_utc=request.observed_at_utc,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
            evidence_id=request.evidence_id,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.evidence_attached", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/investigate", response_model=FailedDebitCaseResponse)
async def record_failed_debit_investigation(
    dispute_id: str,
    request: RecordFailedDebitInvestigationRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:investigation:write",))
    policy.require_role(principal, roles=("dispute_operations_analyst",))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().record_investigation(
        RecordInvestigationOutcomeCommand(
            dispute_id=dispute_id,
            analyst_notes=request.analyst_notes,
            simulated_bank_status=request.simulated_bank_status,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.investigation_recorded", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/investigation", response_model=FailedDebitCaseResponse, include_in_schema=False)
async def record_failed_debit_investigation_compat(
    dispute_id: str,
    request: RecordFailedDebitInvestigationRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    return await record_failed_debit_investigation(
        dispute_id=dispute_id,
        request=request,
        principal=principal,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )


@app.post("/v1/disputes/{dispute_id}/classify", response_model=FailedDebitCaseResponse)
async def classify_failed_debit_case(
    dispute_id: str,
    request: ClassifyFailedDebitCaseRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:classify:write",))
    policy.require_role(principal, roles=("dispute_operations_analyst",))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().classify_case(
        ClassifyFailedDebitCaseCommand(
            dispute_id=dispute_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.case_classified", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/human-review", response_model=FailedDebitCaseResponse)
async def request_failed_debit_human_review(
    dispute_id: str,
    request: RequestFailedDebitHumanReviewRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:review:write",))
    policy.require_role(principal, roles=("dispute_operations_analyst",))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().request_human_review(
        RequestFailedDebitHumanReviewCommand(
            dispute_id=dispute_id,
            reason_code=request.reason_code,
            rationale=request.rationale,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.human_review_requested", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/review-decisions", response_model=FailedDebitCaseResponse)
async def record_failed_debit_review_decision(
    dispute_id: str,
    request: RecordFailedDebitReviewDecisionRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:review:write",))
    policy.require_role(principal, roles=("supervisor_approver",))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().record_review_decision(
        RecordFailedDebitReviewDecisionCommand(
            dispute_id=dispute_id,
            decision=request.decision,
            reason_code=request.reason_code,
            rationale=request.rationale,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            approved_disposition=request.approved_disposition,
            review_id=request.review_id,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.review_decision_recorded", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/disposition", response_model=FailedDebitCaseResponse)
async def record_failed_debit_disposition(
    dispute_id: str,
    request: RecordFailedDebitDispositionRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:disposition:write",))
    policy.require_role(principal, roles=("dispute_operations_analyst", "supervisor_approver"))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().record_disposition(
        RecordFailedDebitDispositionCommand(
            dispute_id=dispute_id,
            disposition=request.disposition,
            reason_code=request.reason_code,
            rationale=request.rationale,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.disposition_recorded", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/close", response_model=FailedDebitCaseResponse)
async def close_failed_debit_case(
    dispute_id: str,
    request: CloseFailedDebitCaseRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:close:write",))
    policy.require_role(principal, roles=("supervisor_approver",))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().close_case(
        CloseFailedDebitCaseCommand(
            dispute_id=dispute_id,
            reason_code=request.reason_code,
            rationale=request.rationale,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.case_closed", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.post("/v1/disputes/{dispute_id}/quarantine", response_model=FailedDebitCaseResponse)
async def quarantine_failed_debit_case(
    dispute_id: str,
    request: QuarantineFailedDebitCaseRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:quarantine:write",))
    policy.require_role(principal, roles=("supervisor_approver", "audit_reviewer"))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().quarantine_case(
        QuarantineFailedDebitCaseCommand(
            dispute_id=dispute_id,
            reason_code=request.reason_code,
            rationale=request.rationale,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            actor_subject=principal.subject,
            actor_role=principal.primary_role,
            expected_version=request.expected_version,
        )
    )
    METRICS.record_business_event(event_type="failed_debit.case_quarantined", outcome="success")
    return FailedDebitCaseResponse.from_detail(detail)


@app.get("/v1/disputes/{dispute_id}/history", response_model=FailedDebitTimelineResponse)
async def get_failed_debit_history(
    dispute_id: str,
    principal: Principal = Depends(local_principal_dependency),
) -> FailedDebitTimelineResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:history:read",))
    policy.require_role(principal, roles=("audit_reviewer", "supervisor_approver"))
    detail = _failed_debit_service().get_history(dispute_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    return FailedDebitTimelineResponse.model_validate(
        {
            "dispute_id": detail["dispute_id"],
            "version": detail["version"],
            "state": detail["state"],
            "evidence": detail["evidence"],
            "timeline": detail["timeline"],
            "review_history": detail["review_history"],
            "audit_integrity_checks": detail["audit_integrity_checks"],
            "audit_link_hash": detail["audit_link_hash"],
        }
    )


@app.get("/v1/disputes/{dispute_id}/timeline", response_model=FailedDebitTimelineResponse, include_in_schema=False)
async def get_failed_debit_timeline_compat(
    dispute_id: str,
    principal: Principal = Depends(local_principal_dependency),
) -> FailedDebitTimelineResponse:
    return await get_failed_debit_history(dispute_id=dispute_id, principal=principal)


@app.get("/v1/disputes/{dispute_id}/audit-integrity", response_model=FailedDebitAuditIntegrityResponse)
async def verify_failed_debit_audit_integrity(
    dispute_id: str,
    principal: Principal = Depends(local_principal_dependency),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitAuditIntegrityResponse:
    policy = LocalAuthorizationPolicy()
    policy.require(principal, scopes=("dispute:audit:read",))
    policy.require_role(principal, roles=("audit_reviewer", "supervisor_approver"))
    current = _failed_debit_service().get_case(dispute_id)
    if current is None:
        raise HTTPException(status_code=404, detail="failed-debit dispute not found")
    detail = _failed_debit_service().verify_audit_integrity(
        dispute_id=dispute_id,
        actor_subject=principal.subject,
        actor_role=principal.primary_role,
        correlation_id=correlation_id,
    )
    outcome = "success" if detail["passed"] else "error"
    METRICS.record_business_event(event_type="failed_debit.audit_integrity_verified", outcome=outcome)
    return FailedDebitAuditIntegrityResponse.model_validate(detail)


@app.post("/v1/disputes/{dispute_id}/resolution", response_model=FailedDebitCaseResponse, include_in_schema=False)
async def propose_failed_debit_resolution_compat(
    dispute_id: str,
    request: ProposeFailedDebitResolutionRequest,
    principal: Principal = Depends(local_principal_dependency),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str = Header(default="local", alias="X-Correlation-Id"),
) -> FailedDebitCaseResponse:
    if request.finalize_action != "propose_only":
        raise HTTPException(
            status_code=400,
            detail="compatibility resolution path no longer supports finalization; use classify/review/disposition/close",
        )
    return await classify_failed_debit_case(
        dispute_id=dispute_id,
        request=ClassifyFailedDebitCaseRequest(expected_version=request.expected_version),
        principal=principal,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
