from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from factory.operator_portal.web_ui.app import create_web_ui_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_debug_plan_live_http_routes(tmp_path: Path) -> None:
    client = TestClient(create_web_ui_app(project_root=PROJECT_ROOT, portfolio_state_root=tmp_path / "portfolio"))
    response = client.get("/operator-portal/api/debug-plan/factory")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "upi-app-factory.debug-plan.v1"
    assert payload["plan_kind"] == "factory"
    download = client.get("/operator-portal/api/debug-plan/factory/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/json")
