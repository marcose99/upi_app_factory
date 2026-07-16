from __future__ import annotations

from pathlib import Path
import socket
import time
from typing import Iterator

import pytest

from factory.application_engineering.portfolio import (
    PolicyContract,
    PortfolioCatalogue,
    PortfolioStore,
    PortfolioSupervisor,
    QuotaContract,
    RegistrationRequest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PortfolioFixture = tuple[PortfolioStore, PortfolioCatalogue, PortfolioSupervisor, list[int]]


@pytest.fixture()
def portfolio(tmp_path: Path) -> Iterator[PortfolioFixture]:
    state_root = tmp_path / "phase51_state"
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=state_root)
    catalogue = PortfolioCatalogue(store=store)
    supervisor = PortfolioSupervisor(store=store, catalogue=catalogue)
    ports: list[int] = []
    try:
        yield store, catalogue, supervisor, ports
    finally:
        supervisor.stop_all()
        wait_for_ports_closed(ports)
        assert not any(port_open(port) for port in ports)


def registration(
    *,
    app_id: str,
    version_id: str = "v1",
    generated_run_id: str | None = None,
    app_root: Path,
    requirements: str = "phase51 mock requirements",
    source_commit: str = "phase51-test",
    manifest: dict[str, object] | None = None,
    capabilities: tuple[str, ...] = ("echo",),
    quota: QuotaContract = QuotaContract(),
    policy: PolicyContract = PolicyContract(),
) -> RegistrationRequest:
    return RegistrationRequest(
        app_id=app_id,
        version_id=version_id,
        generated_run_id=generated_run_id or f"{app_id}_{version_id}_run",
        requirements=requirements,
        source_commit=source_commit,
        evidence={
            "generated_run_id": generated_run_id or f"{app_id}_{version_id}_run",
            "mock": True,
        },
        manifest=manifest
        or {"openapi": {"paths": {"/health": {}, "/scenario/echo": {}, "/capabilities": {}}}},
        entrypoint="mock_app.main:app",
        application_root=app_root,
        capabilities=capabilities,
        quota=quota,
        policy=policy,
    )


def mock_app(tmp_path: Path, name: str, label: str, *, crash_health: bool = False) -> Path:
    root = tmp_path / name
    package = root / "mock_app"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    health_body = (
        'raise RuntimeError("crash storm")'
        if crash_health
        else f'return {{"status": "ok", "app": "{label}", "mock_only": True}}'
    )
    (package / "main.py").write_text(
        f'''
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Phase 51 Mock {label}")

@app.get("/health")
async def health():
    {health_body}

@app.get("/runtime/health")
async def runtime_health():
    return {{"status": "passed", "app": "{label}"}}

@app.get("/capabilities")
async def capabilities():
    return {{
        "mock_only": True,
        "capabilities": ["echo"],
        "live_provider_calls_allowed": False,
        "default_runtime_llm_calls": 0,
    }}

@app.post("/scenario/echo")
async def echo(request: Request):
    payload = await request.json()
    if "client_request_id" not in payload or "amount" not in payload:
        return JSONResponse(status_code=422, content={{"error": {{"code": "validation_error"}}}})
    return {{
        "accepted": True,
        "client_request_id": payload["client_request_id"],
        "amount": payload["amount"],
        "app": "{label}",
    }}

@app.get("/missing")
async def missing():
    return JSONResponse(status_code=404, content={{"error": {{"code": "not_found"}}}})
''',
        encoding="utf-8",
    )
    return root


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_ports_closed(ports: list[int], *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and any(port_open(port) for port in ports):
        time.sleep(0.1)
