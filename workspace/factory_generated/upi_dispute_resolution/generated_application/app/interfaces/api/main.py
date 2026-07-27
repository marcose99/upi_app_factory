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
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
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


async def local_principal_dependency(
    authorization: str | None = Header(default=None, alias="Authorization"),
    subject: str | None = Header(default=None, alias="X-Local-Subject"),
    roles: str = Header(default="", alias="X-Local-Roles"),
    scopes: str = Header(default="", alias="X-Local-Scopes"),
) -> Principal:
    return local_principal(
        authorization=authorization,
        subject=subject,
        roles=roles,
        scopes=scopes,
    )


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
    service = DisputeService(SqliteUnitOfWork(DATABASE_PATH))
    dispute_id = service.create_dispute(
        CreateDisputeCommand(
            transaction_ref=request.transaction_ref,
            customer_upi=request.customer_upi,
            reason=request.reason,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            owner_subject=principal.subject,
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
