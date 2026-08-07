from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from generated_application.app.domain.exceptions import (
    DomainError,
    DuplicateBusinessSubmissionError,
    IdempotencyConflictError,
)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    correlation_id = request.headers.get("x-correlation-id", "missing")
    status_code = 409 if isinstance(exc, (DuplicateBusinessSubmissionError, IdempotencyConflictError)) else 400
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
