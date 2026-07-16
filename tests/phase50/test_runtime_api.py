from __future__ import annotations

import asyncio
from pathlib import Path
import secrets
from typing import Any, cast

import httpx
from fastapi import FastAPI

from factory.operator_portal.local_web_api import create_app
from factory.operator_portal.runtime_contracts import RUNTIME_APPROVAL_TOKEN


PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def _request(app: FastAPI, method: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-portal") as client:
        return await client.request(method, path, json=payload)


def request(app: FastAPI, method: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    return asyncio.run(_request(app, method, path, payload))


def test_runtime_api_blocks_wrong_approval_and_replay(tmp_path: Path) -> None:
    app = create_app(project_root=PROJECT_ROOT, runtime_state_root=tmp_path / "runtime")
    run_id = f"phase50_api_{secrets.token_hex(4)}"
    wrong = request(
        app,
        "POST",
        f"/operator-portal/api/runtime/runs/{run_id}/approvals",
        {"action": "stop", "approval_token": "wrong"},
    )
    assert wrong.status_code == 403
    assert RUNTIME_APPROVAL_TOKEN not in wrong.text

    approved = request(
        app,
        "POST",
        f"/operator-portal/api/runtime/runs/{run_id}/approvals",
        {"action": "stop", "approval_token": RUNTIME_APPROVAL_TOKEN, "nonce": "nonce-123456"},
    )
    assert approved.status_code == 200
    assert "approval_token" not in approved.text

    stopped = request(
        app,
        "POST",
        f"/operator-portal/api/runtime/runs/{run_id}/stop",
        {"approval_nonce": "nonce-123456", "port": 18042},
    )
    assert stopped.status_code == 202
    replay = request(
        app,
        "POST",
        f"/operator-portal/api/runtime/runs/{run_id}/stop",
        {"approval_nonce": "nonce-123456", "port": 18042},
    )
    assert replay.status_code == 403


def test_catalog_and_view_are_rendered() -> None:
    app = create_app(project_root=PROJECT_ROOT)
    catalog = request(app, "GET", "/operator-portal/api/runtime/scenario-catalog")
    assert catalog.status_code == 200
    payload = cast(dict[str, Any], catalog.json())
    assert {"positive", "negative", "boundary", "idempotency", "resilience", "timeout", "security"}.issubset(
        set(payload["categories"])
    )
    view = request(app, "GET", "/operator-portal/api/runtime/runs/phase50_view/view")
    assert view.status_code == 200
    assert "Runtime Operations" in view.text
