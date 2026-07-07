#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from fastapi.testclient import TestClient

from scripts.build_operator_portal_dashboard_panels import (
    PANEL_IDS,
    READY,
    build_operator_portal_dashboard_panels,
    validate_operator_portal_dashboard_panels,
)
from scripts.start_factory_operator_portal import create_app


POLICY_PATH = Path("policies/phase13ay_operator_portal_dashboard_policy.json")
DOC_PATH = Path("docs/phase13ay/operator_portal_evidence_dashboards.md")
BUILDER_PATH = Path("scripts/build_operator_portal_dashboard_panels.py")
PORTAL_PATH = Path("scripts/start_factory_operator_portal.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ay/operator_portal_dashboard_audit.json"
)
PHASE13AX_PREVIEW = Path("scripts/build_guided_requirement_intake_preview.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, BUILDER_PATH, PORTAL_PATH, AUDIT_PATH, PHASE13AX_PREVIEW]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)
    if policy.get("schema_version") != "operator-portal-dashboard-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_OPERATOR_PORTAL_DASHBOARDS_READ_ONLY":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13ax_requirement_intake_ui") is not True:
        failures.append("Policy must require Phase 13AX")
    if policy.get("read_only_dashboards") is not True:
        failures.append("Policy must keep dashboards read-only")
    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "arbitrary_shell_execution_allowed_from_ui",
        "destructive_delete_allowed_from_ui",
        "real_generated_application_write_allowed_from_ui",
        "requirement_package_write_allowed_from_ui",
        "generation_execution_allowed_from_ui",
        "factory_self_modification_allowed_from_ui",
        "auto_merge_allowed_from_ui",
        "auto_tag_allowed_from_ui",
        "auto_release_allowed_from_ui",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")
    if set(policy.get("required_dashboard_panels", [])) != set(PANEL_IDS):
        failures.append("Policy dashboard panels do not match builder")
    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "arbitrary_shell_execution_exposed_from_ui",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "requirement_package_written_from_ui",
        "application_generation_triggered_from_ui",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    dashboard_status = build_operator_portal_dashboard_panels(Path.cwd())
    if dashboard_status.get("status") != READY:
        failures.append("Dashboard status should be ready")
    failures.extend(validate_operator_portal_dashboard_panels(dashboard_status))

    client = TestClient(create_app(Path.cwd()))
    api = client.get("/api/dashboards")
    if api.status_code != 200:
        failures.append("Dashboard API failed")
    else:
        payload = api.json()
        if set(panel["panel_id"] for panel in payload.get("panels", [])) != set(PANEL_IDS):
            failures.append("Dashboard API missing required panels")
        if payload.get("arbitrary_shell_execution_exposed_from_ui") is not False:
            failures.append("Dashboard API must keep shell execution disabled")

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
        if response.status_code != 200:
            failures.append(f"Dashboard route failed: {route}")

    cli = subprocess.run(
        [sys.executable, str(BUILDER_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Dashboard builder CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Dashboard builder CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "operator portal evidence and governance dashboards",
        "read-only",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not execute arbitrary shell commands from the ui",
        "dashboard routes",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AY validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 13AY operator portal dashboard artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
