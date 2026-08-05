from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from generated_application.app.domain.exceptions import (
    DomainError,
    DuplicateBusinessSubmissionError,
    IdempotencyConflictError,
    OptimisticConcurrencyError,
)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    correlation_id = request.headers.get("x-correlation-id", "missing")
    status_code = (
        409
        if isinstance(
            exc,
            (
                DuplicateBusinessSubmissionError,
                IdempotencyConflictError,
                OptimisticConcurrencyError,
            ),
        )
        else 400
    )
    _record_rejection_audit(request, status_code=status_code, code=exc.__class__.__name__, detail=str(exc))
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": "https://upi-app-factory.local/problems/domain_error",
            "title": "Domain Error",
            "status": status_code,
            "detail": str(exc),
            "instance": request.url.path,
            "code": exc.__class__.__name__,
            "correlation_id": correlation_id,
            "boundary_notice": "Local mock/simulated generated application only.",
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    correlation_id = request.headers.get("x-correlation-id", "missing")
    if exc.status_code in {400, 403, 409}:
        _record_rejection_audit(
            request,
            status_code=exc.status_code,
            code="HTTPException",
            detail=str(exc.detail),
        )
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": "https://upi-app-factory.local/problems/http_error",
            "title": "HTTP Error",
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": request.url.path,
            "code": "HTTPException",
            "correlation_id": correlation_id,
            "boundary_notice": "Local mock/simulated generated application only.",
        },
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    correlation_id = request.headers.get("x-correlation-id", "missing")
    invalid_params = []
    for error in exc.errors():
        invalid_params.append(
            {
                "loc": [str(item) for item in error.get("loc", [])],
                "msg": str(error.get("msg", "validation error")),
                "type": str(error.get("type", "validation_error")),
            }
        )
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content={
            "type": "https://upi-app-factory.local/problems/validation_error",
            "title": "Validation Error",
            "status": 422,
            "detail": "Request validation failed.",
            "instance": request.url.path,
            "code": "RequestValidationError",
            "correlation_id": correlation_id,
            "invalid_params": invalid_params,
            "boundary_notice": "Local mock/simulated generated application only.",
        },
    )


def _record_rejection_audit(
    request: Request,
    *,
    status_code: int,
    code: str,
    detail: str,
) -> None:
    if status_code not in {400, 403, 409}:
        return
    if not request.url.path.startswith(("/disputes", "/v1/disputes")):
        return
    database_path = getattr(request.app.state, "database_path", None)
    if not isinstance(database_path, Path):
        return
    category = _rejection_category(status_code=status_code, code=code, detail=detail)
    principal = getattr(request.state, "principal", None)
    actor_id = str(getattr(principal, "subject", "anonymous"))
    actor_role = str(getattr(principal, "primary_role", "unknown"))
    idempotency_key = request.headers.get("Idempotency-Key", "")
    payload = {
        "category": category,
        "status_code": status_code,
        "error_code": code,
        "detail_redacted": True,
        "reason_sha256": hashlib.sha256(detail.encode("utf-8")).hexdigest(),
        "correlation_id": request.headers.get("x-correlation-id", "missing"),
        "method": request.method,
        "path": request.url.path,
        "idempotency_key_sha256": (
            hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None
        ),
    }
    try:
        from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import (
            SqliteUnitOfWork,
        )

        with SqliteUnitOfWork(database_path) as uow:
            uow.audit.append(
                actor_id,
                actor_role,
                f"rejection.{category}",
                request.url.path,
                payload,
            )
            uow.commit()
    except Exception:
        return


def _rejection_category(*, status_code: int, code: str, detail: str) -> str:
    lowered = detail.lower()
    if code == "IdempotencyConflictError":
        return "idempotency_conflict"
    if "segregation of duties" in lowered:
        return "segregation_of_duties_failure"
    if status_code == 403:
        return "prohibited_action"
    return "rejected_action"
