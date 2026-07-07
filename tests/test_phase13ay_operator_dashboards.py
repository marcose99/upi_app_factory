from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.build_operator_portal_dashboard_panels import (
    PANEL_IDS,
    READY,
    build_operator_portal_dashboard_panels,
    validate_operator_portal_dashboard_panels,
    write_operator_portal_dashboard_panels,
)
from scripts.start_factory_operator_portal import create_app


def test_dashboard_panels_cover_required_sections() -> None:
    status = build_operator_portal_dashboard_panels(Path.cwd())
    panels = status["panels"]
    assert isinstance(panels, list)
    assert {panel["panel_id"] for panel in panels} == set(PANEL_IDS)
    assert validate_operator_portal_dashboard_panels(status) == []


def test_dashboard_panels_are_read_only_and_safe() -> None:
    status = build_operator_portal_dashboard_panels(Path.cwd())
    assert status["read_only_dashboards"] is True
    assert status["arbitrary_shell_execution_exposed_from_ui"] is False
    assert status["live_provider_calls_enabled"] is False
    assert status["external_system_calls_enabled"] is False
    assert status["auto_merge_enabled_from_ui"] is False


def test_dashboard_status_audit_report_is_written(tmp_path: Path) -> None:
    status = build_operator_portal_dashboard_panels(Path.cwd())
    output = tmp_path / "dashboard_status.json"
    write_operator_portal_dashboard_panels(status, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "operator-portal-dashboard-panels.v1"
    assert payload["status"] == READY


def test_dashboard_api_returns_panels() -> None:
    client = TestClient(create_app(Path.cwd()))
    response = client.get("/api/dashboards")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == READY
    assert {panel["panel_id"] for panel in payload["panels"]} == set(PANEL_IDS)


def test_dashboard_pages_render() -> None:
    client = TestClient(create_app(Path.cwd()))
    for route in [
        "/dashboards",
        "/dashboards/evidence",
        "/dashboards/standards",
        "/dashboards/self-healing",
        "/dashboards/threats",
        "/dashboards/handover",
        "/dashboards/generated-app",
    ]:
        response = client.get(route)
        assert response.status_code == 200
        assert "Portal execution remains disabled" in response.text


def test_dashboard_builder_cli_exits_success() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_operator_portal_dashboard_panels.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == READY


def test_phase13ay_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ay_operator_dashboards.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AY operator portal dashboard artifacts validated." in result.stdout
