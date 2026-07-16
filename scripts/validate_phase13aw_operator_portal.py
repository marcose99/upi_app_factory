#!/usr/bin/env python3
"""Validate Phase 13AW local Factory Operator Portal artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import httpx

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_local_operator_portal_status import (  # noqa: E402
    PORTAL_SECTIONS,
    build_local_operator_portal_status,
    validate_local_operator_portal_status,
)
from scripts.start_factory_operator_portal import create_app  # noqa: E402


POLICY_PATH = Path("policies/phase13aw_local_operator_portal_policy.json")
DOC_PATH = Path("docs/phase13aw/local_factory_operator_portal.md")
STATUS_PATH = Path("scripts/build_local_operator_portal_status.py")
PORTAL_PATH = Path("scripts/start_factory_operator_portal.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13aw/local_operator_portal_audit.json"
)
PHASE13AV_SUITE = Path("scripts/build_local_agentic_ai_threat_tests.py")


def portal_request(path: str, *, method: str = "GET", json_payload: dict[str, Any] | None = None) -> httpx.Response:
    import asyncio

    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(Path.cwd()))
        async with httpx.AsyncClient(transport=transport, base_url="http://local-portal") as client:
            return await client.request(method, path, json=json_payload)

    return asyncio.run(_request())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, STATUS_PATH, PORTAL_PATH, AUDIT_PATH, PHASE13AV_SUITE]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "local-operator-portal-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_OPERATOR_PORTAL_READ_ONLY_FOUNDATION":
        failures.append("Policy mode mismatch")
    if policy.get("portal_host") != "127.0.0.1":
        failures.append("Portal host must be local loopback")
    if policy.get("portal_port") != 8088:
        failures.append("Portal port must be 8088")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13av_agentic_threat_tests") is not True:
        failures.append("Policy must require Phase 13AV threat tests")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "arbitrary_shell_execution_allowed_from_ui",
        "destructive_delete_allowed_from_ui",
        "real_generated_application_write_allowed_from_ui",
        "factory_self_modification_allowed_from_ui",
        "auto_merge_allowed_from_ui",
        "auto_tag_allowed_from_ui",
        "auto_release_allowed_from_ui",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("portal_sections_required", [])) != set(PORTAL_SECTIONS):
        failures.append("Policy portal sections do not match status sections")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "arbitrary_shell_execution_exposed_from_ui",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    status = build_local_operator_portal_status(Path.cwd())
    failures.extend(validate_local_operator_portal_status(status))

    health = portal_request("/health")
    if health.status_code != 200 or health.json().get("status") != "ok":
        failures.append("Portal health endpoint failed")

    status_response = portal_request("/api/status")
    if status_response.status_code != 200:
        failures.append("Portal status endpoint failed")
    else:
        status_json = status_response.json()
        if status_json.get("arbitrary_shell_execution_exposed_from_ui") is not False:
            failures.append("Portal status must keep arbitrary shell execution disabled")

    evidence_response = portal_request("/api/evidence")
    if evidence_response.status_code != 200:
        failures.append("Portal evidence endpoint failed")

    commands_response = portal_request("/api/safe-commands")
    if commands_response.status_code != 200:
        failures.append("Portal safe commands endpoint failed")
    else:
        commands = commands_response.json()
        if not commands:
            failures.append("Portal safe commands endpoint returned no commands")
        for command in commands:
            if command.get("execution_enabled_in_portal") is not False:
                failures.append("Portal command execution must remain disabled")

    dashboard = portal_request("/")
    if dashboard.status_code != 200:
        failures.append("Portal dashboard endpoint failed")
    elif "Factory Operator Portal" not in dashboard.text:
        failures.append("Portal dashboard missing title")

    cli = subprocess.run(
        [sys.executable, str(STATUS_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Portal status CLI should pass")
    elif "LOCAL_OPERATOR_PORTAL_STATUS_READY" not in cli.stdout:
        failures.append("Portal status CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "local factory operator portal foundation",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not execute arbitrary shell commands from the ui",
        "portal sections",
        "start command",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AW validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AW local Factory Operator Portal artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
