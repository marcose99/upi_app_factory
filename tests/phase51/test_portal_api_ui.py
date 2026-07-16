from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PortfolioCatalogue,
    PortfolioStore,
    PortfolioSupervisor,
)
from factory.operator_portal.local_web_api import create_app
from factory.operator_portal.portfolio_api import render_portfolio_view
from tests.phase51.conftest import (
    PROJECT_ROOT,
    free_port,
    mock_app,
    port_open,
    registration,
    wait_for_ports_closed,
)


def test_portal_api_exposes_catalogue_runtime_scenarios_and_html_view(tmp_path: Path) -> None:
    state_root = tmp_path / "portal_state"
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=state_root)
    catalogue = PortfolioCatalogue(store=store)
    version = catalogue.register(
        registration(
            app_id="portal_api_app",
            app_root=mock_app(tmp_path, "portal_api_app", "portal"),
        )
    )
    port = free_port()
    app = create_app(
        project_root=PROJECT_ROOT,
        runtime_state_root=tmp_path / "phase50",
        portfolio_state_root=state_root,
    )
    client = TestClient(app)
    try:
        catalogue_payload = client.get("/operator-portal/api/portfolio/catalogue").json()
        assert catalogue_payload["versions"][0]["app_id"] == "portal_api_app"
        approval = client.post(
            "/operator-portal/api/portfolio/approvals",
            json={
                "action": "start",
                "scope": "portal_api_runtime_001",
                "actor": "tester",
                "approval_token": LOCAL_APPROVAL_TOKEN,
                "nonce": "nonce_portal_start",
            },
        )
        assert approval.status_code == 200
        start = client.post(
            "/operator-portal/api/portfolio/runtime/start",
            json={
                "app_id": version.app_id,
                "version_id": version.version_id,
                "run_id": "portal_api_runtime_001",
                "port": port,
                "approval_nonce": "nonce_portal_start",
            },
        )
        assert start.status_code == 202
        assert start.json()["state"] == "READY"
        scenarios = client.post(
            "/operator-portal/api/portfolio/scenarios",
            json={
                "app_id": version.app_id,
                "version_id": version.version_id,
                "run_id": "portal_api_runtime_001",
                "port": port,
            },
        )
        assert scenarios.json()["decision"] == "GO"
        view = client.get("/operator-portal/api/portfolio/view")
        assert "Governed Portfolio Operations" in view.text
        assert "portal_api_app" in view.text
    finally:
        PortfolioSupervisor(store=store, catalogue=catalogue).stop_all()
        wait_for_ports_closed([port])
        assert not port_open(port)


def test_rendered_portfolio_ui_escapes_catalogue_and_runtime_fields() -> None:
    html = render_portfolio_view(
        {
            "versions": [
                {
                    "app_id": "<script>alert(1)</script>",
                    "version_id": "v1",
                    "state": "active",
                    "generated_run_id": "run_001",
                    "evidence_checksum": "<b>checksum</b>",
                }
            ]
        },
        [
            {
                "binding": {
                    "run_id": "runtime_001",
                    "app_id": "safe_app",
                    "version_id": "v1",
                    "host": "127.0.0.1",
                    "port": 18051,
                },
                "state": "READY",
            }
        ],
    )

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;checksum&lt;/b&gt;" in html
