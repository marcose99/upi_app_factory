from __future__ import annotations

import importlib
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

_API_MODULE = "factory.operator_portal.local_web_api"
_API_VARIABLE = "app"
_STATIC_ROOT = Path(__file__).resolve().parent / "web_ui" / "static"

_module = importlib.import_module(_API_MODULE)
_api_app = cast(FastAPI, getattr(_module, _API_VARIABLE))

app = FastAPI(
    title="UPI App Factory Operator Portal",
    description=(
        "Local-first governed control plane with mock-safe application "
        "engineering, evidence and download capabilities."
    ),
    version="1.0.0-rc",
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/operator-portal", response_class=HTMLResponse, include_in_schema=False)
async def operator_portal_ui() -> HTMLResponse:
    return HTMLResponse((_STATIC_ROOT / "index.html").read_text(encoding="utf-8"))


@app.get("/app.js", response_class=FileResponse, include_in_schema=False)
async def operator_portal_script() -> FileResponse:
    return FileResponse(_STATIC_ROOT / "app.js", media_type="application/javascript")


@app.get("/styles.css", response_class=FileResponse, include_in_schema=False)
async def operator_portal_styles() -> FileResponse:
    return FileResponse(_STATIC_ROOT / "styles.css", media_type="text/css")


@app.get("/operator-portal/health")
async def operator_portal_health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": "mock-safe-local",
        "real_payment_calls": "disabled",
        "llm_calls": 0,
    }


app.include_router(_api_app.router)
