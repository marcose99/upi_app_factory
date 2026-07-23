from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from factory.operator_portal.web_ui.app import create_web_ui_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_documentation_live_http_routes(tmp_path: Path) -> None:
    client = TestClient(create_web_ui_app(project_root=PROJECT_ROOT, portfolio_state_root=tmp_path / "portfolio"))
    response = client.get("/operator-portal/api/documentation/factory")
    assert response.status_code == 200
    assert "UPI App Factory Complete Guide" in response.text
    download = client.get("/operator-portal/api/documentation/factory/download")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
