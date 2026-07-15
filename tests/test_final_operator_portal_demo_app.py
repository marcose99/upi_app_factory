from __future__ import annotations

from fastapi.testclient import TestClient

from factory.operator_portal.final_demo_app import app


def test_final_operator_portal_serves_interactive_html() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "UPI App Factory" in response.text
    assert "API explorer" in response.text
    assert "Requirements intake" in response.text
    assert "Download & evidence centre" in response.text
    assert "FactoryFromNothing" not in response.text
    assert "upi_dispute_resolution_factory" not in response.text


def test_final_operator_portal_health_is_mock_safe() -> None:
    response = TestClient(app).get("/operator-portal/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "mock-safe-local",
        "real_payment_calls": "disabled",
        "llm_calls": 0,
    }


def test_final_operator_portal_openapi_includes_underlying_api() -> None:
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"] == "UPI App Factory Operator Portal"
    paths = document["paths"]
    assert "/operator-portal/health" in paths
    assert len(paths) >= 2
    assert any(
        token in path.lower()
        for path in paths
        for token in ("download", "export", "bundle", "evidence")
    )
