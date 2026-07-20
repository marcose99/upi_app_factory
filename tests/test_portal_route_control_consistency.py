from __future__ import annotations

from pathlib import Path

from factory.operator_portal.local_web_api import create_app
from tests.test_phase36_operator_portal_local_web_ui import request


def test_health_routes_are_consistent_and_local_only(tmp_path: Path) -> None:
    app = create_app(
        project_root=tmp_path,
        browser_state_root=tmp_path / "runs",
        portfolio_state_root=tmp_path / "portfolio",
        runtime_state_root=tmp_path / "runtime",
        phase69_state_root=tmp_path / "phase69",
    )

    root_health = request(app, "GET", "/health")
    portal_health = request(app, "GET", "/operator-portal/health")

    assert root_health.status_code == 200
    assert portal_health.status_code == 200
    assert root_health.json() == portal_health.json()
    boundaries = root_health.json()["safety_boundaries"]
    assert boundaries["local_only"] is True
    assert boundaries["live_provider_calls_allowed"] is False
    assert boundaries["external_ecosystem_integrations"] == "mocked_or_simulated_only"


def test_route_methods_match_control_contract_without_live_operations(tmp_path: Path) -> None:
    app = create_app(
        project_root=tmp_path,
        browser_state_root=tmp_path / "runs",
        portfolio_state_root=tmp_path / "portfolio",
    )
    route_methods = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()))
        for route in app.routes
    }

    assert route_methods["/operator-portal/api/runs"] == {"POST"}
    assert route_methods["/operator-portal/api/runs/{run_id}/plan"] == {"POST"}
    assert route_methods["/operator-portal/api/runs/{run_id}/approvals"] == {"POST"}
    assert route_methods["/operator-portal/api/runs/{run_id}/execute"] == {"POST"}
    assert route_methods["/operator-portal/api/runs/{run_id}/cancel"] == {"POST"}
    assert route_methods["/operator-portal/api/portfolio/runtime/start"] == {"POST"}
    assert route_methods["/operator-portal/api/portfolio/runtime/stop-all"] == {"POST"}

    forbidden_fragments = ("deploy", "push", "tag", "merge", "provider", "payment")
    assert not [
        path
        for path in route_methods
        if any(fragment in path.lower() for fragment in forbidden_fragments)
    ]
