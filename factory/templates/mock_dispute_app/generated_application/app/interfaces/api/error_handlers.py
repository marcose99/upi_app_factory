from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from generated_application.app.domain.exceptions import DomainError


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    correlation_id = request.headers.get("x-correlation-id", "missing")
    return JSONResponse(
        status_code=400,
        content={
            "error_code": exc.__class__.__name__,
            "message": str(exc),
            "correlation_id": correlation_id,
        },
    )
