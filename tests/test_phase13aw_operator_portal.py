from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.build_local_operator_portal_status import (
    PORTAL_SECTIONS,
    build_local_operator_portal_status,
    validate_local_operator_portal_status,
    write_local_operator_portal_status,
)
from scripts.start_factory_operator_portal import create_app


def test_portal_status_has_required_sections() -> None:
    status = build_local_operator_portal_status(Path.cwd())

    assert set(status["sections"]) == set(PORTAL_SECTIONS)
    assert validate_local_operator_portal_status(status) == []


def test_portal_status_keeps_unsafe_actions_disabled() -> None:
    status = build_local_operator_portal_status(Path.cwd())

    assert status["arbitrary_shell_execution_exposed_from_ui"] is False
    assert status["auto_merge_enabled_from_ui"] is False
    assert status["auto_tag_enabled_from_ui"] is False
    assert status["auto_release_enabled_from_ui"] is False
    assert status["external_system_calls_enabled"] is False


def test_safe_command_catalog_is_display_only() -> None:
    status = build_local_operator_portal_status(Path.cwd())

    commands = status["safe_command_catalog"]
    assert commands
    assert all(command["execution_enabled_in_portal"] is False for command in commands)
    assert all(command["requires_human_terminal_execution"] is True for command in commands)


def test_portal_health_endpoint() -> None:
    client = TestClient(create_app(Path.cwd()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "read-only"


def test_portal_status_endpoint() -> None:
    client = TestClient(create_app(Path.cwd()))

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "local-operator-portal-status.v1"
    assert payload["arbitrary_shell_execution_exposed_from_ui"] is False


def test_portal_evidence_endpoint() -> None:
    client = TestClient(create_app(Path.cwd()))

    response = client.get("/api/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload


def test_portal_safe_commands_endpoint() -> None:
    client = TestClient(create_app(Path.cwd()))

    response = client.get("/api/safe-commands")

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(command["execution_enabled_in_portal"] is False for command in payload)


def test_portal_dashboard_renders_html() -> None:
    client = TestClient(create_app(Path.cwd()))

    response = client.get("/")

    assert response.status_code == 200
    assert "Factory Operator Portal" in response.text
    assert "Portal command execution is disabled" in response.text


def test_portal_status_audit_report_is_written(tmp_path: Path) -> None:
    status = build_local_operator_portal_status(Path.cwd())
    output = tmp_path / "portal_status.json"

    write_local_operator_portal_status(status, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "local-operator-portal-status.v1"
    assert payload["app_id"] == "upi_dispute_resolution"


def test_phase13aw_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13aw_operator_portal.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AW local Factory Operator Portal artifacts validated." in result.stdout
