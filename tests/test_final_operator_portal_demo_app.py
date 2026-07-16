from __future__ import annotations

import asyncio

import httpx

from factory.operator_portal.final_demo_app import app


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-portal") as client:
        return await client.get(path)


def get(path: str) -> httpx.Response:
    return asyncio.run(_get(path))


def test_final_operator_portal_serves_interactive_html() -> None:
    response = get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "UPI App Factory" in response.text
    assert "Requirements Intake" in response.text
    assert "Download Center" in response.text
    assert "Validate Requirements" in response.text
    assert 'id="requirements-input"' in response.text
    assert "Factory" + "FromNothing" not in response.text
    assert "upi_dispute_resolution" + "_factory" not in response.text


def test_final_operator_portal_health_is_mock_safe() -> None:
    response = get("/operator-portal/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "mock-safe-local",
        "real_payment_calls": "disabled",
        "llm_calls": 0,
    }


def test_final_operator_portal_openapi_includes_underlying_api() -> None:
    response = get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"] == "UPI App Factory Operator Portal"
    paths = document["paths"]
    assert "/operator-portal/health" in paths
    assert "/operator-portal/api/runs" in paths
    assert "/operator-portal/api/runs/{run_id}/validation" in paths
    assert len(paths) >= 2
    assert any(
        token in path.lower()
        for path in paths
        for token in ("download", "export", "bundle", "evidence")
    )
