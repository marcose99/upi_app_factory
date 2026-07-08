#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import asyncio
from pathlib import Path
from typing import Any, cast

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.local_web_api import (  # noqa: E402
    LOCAL_API_SAFETY_BOUNDARIES,
    create_app,
)
from factory.operator_portal.validation_runner import ValidationRunnerService  # noqa: E402


APP_ID = "upi_dispute_resolution"
SERVICE_PATH = Path("factory/operator_portal/local_web_api.py")
RUN_SCRIPT_PATH = Path("scripts/run_phase35_operator_portal_local_web_api.py")
POLICY_PATH = Path("policies/phase35_operator_portal_local_web_api_policy.json")
PROMPT_PATH = Path("prompts/phase35/operator_portal_local_web_api_prompt.md")
TEST_PATH = Path("tests/test_phase35_operator_portal_local_web_api.py")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase35"
)

REQUIRED_FILES = [
    SERVICE_PATH,
    RUN_SCRIPT_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    TEST_PATH,
    ARTIFACT_DIR / "operator_portal_local_web_api_gate.json",
    ARTIFACT_DIR / "operator_portal_local_web_api_audit.json",
    ARTIFACT_DIR / "operator_portal_local_web_api_manifest.json",
]

EXPECTED_ENDPOINTS = {
    "GET /health",
    "GET /portal/evidence-dashboard",
    "GET /portal/download-center/status",
    "POST /portal/download-center/export",
    "GET /portal/validation-runner/dry-run",
    "POST /portal/validation-runner/run",
    "GET /portal/validation-runner/latest-report",
}

FORBIDDEN_SOURCE_TERMS = [
    "shell=True",
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "git push",
    "git tag",
    "git merge",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "operator_portal_local_web_api_gate.json")
    audit = load_json(ARTIFACT_DIR / "operator_portal_local_web_api_audit.json")
    manifest = load_json(ARTIFACT_DIR / "operator_portal_local_web_api_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    service_source = SERVICE_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE35-OPERATOR-PORTAL-LOCAL-WEB-API-GATE":
        errors.append("Phase 35 policy missing mandatory local web API gate")
    if policy.get("api_service") != str(SERVICE_PATH):
        errors.append("Phase 35 policy does not identify the local web API service")
    if set(policy.get("endpoints", [])) != EXPECTED_ENDPOINTS:
        errors.append("Phase 35 policy endpoint set does not match the required API")
    if policy.get("local_only") is not True:
        errors.append("Phase 35 policy does not mark the API as local-only")
    if policy.get("local_readiness_scope") != "local_operator_portal_api_only":
        errors.append("Phase 35 policy does not scope readiness to local API readiness only")
    if policy.get("arbitrary_command_execution_allowed") is not False:
        errors.append("Phase 35 policy allows arbitrary command execution")

    for artifact, name in [
        (policy, "policy"),
        (gate, "gate"),
        (audit, "audit"),
        (manifest, "manifest"),
    ]:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 35 {name} changed certification boundary")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 35 {name} claims official certification")
        if artifact.get("official_certification_granted") is not False:
            errors.append(f"Phase 35 {name} claims official certification grant")
        if artifact.get("production_readiness_claimed") is not False:
            errors.append(f"Phase 35 {name} claims production readiness")

    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
    ]:
        if policy.get(field) is not False:
            errors.append(f"Phase 35 policy has invalid safety field: {field}")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 35 policy does not keep ecosystem integrations mocked")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 35 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "local-only FastAPI",
        "GET /health",
        "POST /portal/validation-runner/run",
        "certification_ready_not_certified",
        "must never execute arbitrary command strings",
        "must not fake success",
        "mocked or simulated",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 35 prompt missing required phrase: {phrase}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in service_source:
            errors.append(f"Local web API source includes forbidden term: {term}")


def validate_boundary_payload(payload: dict[str, Any], errors: list[str], context: str) -> None:
    boundaries = payload.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append(f"{context} does not expose safety boundaries")
        return
    safety = cast(dict[str, Any], boundaries)
    for key, expected in LOCAL_API_SAFETY_BOUNDARIES.items():
        if safety.get(key) != expected:
            errors.append(f"{context} changed safety boundary: {key}")


async def _request(
    app: Any,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-operator-portal") as client:
        return await client.request(method, path, json=json_payload)


def request(
    app: Any,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload))


def validate_api_endpoints(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmpdir:
        report_path = Path(tmpdir) / "phase35_validation_report.json"
        runner = ValidationRunnerService(report_path=report_path)
        app = create_app(project_root=PROJECT_ROOT, validation_runner=runner)

        for path in [
            "/health",
            "/portal/evidence-dashboard",
            "/portal/download-center/status",
            "/portal/validation-runner/dry-run",
            "/portal/validation-runner/latest-report",
        ]:
            response = request(app, "GET", path)
            if response.status_code != 200:
                errors.append(f"GET {path} failed with {response.status_code}")
                continue
            validate_boundary_payload(cast(dict[str, Any], response.json()), errors, path)

        dry_run = request(app, "GET", "/portal/validation-runner/dry-run").json()
        dry_report = cast(dict[str, Any], dry_run.get("report", {}))
        if dry_report.get("dry_run") is not True:
            errors.append("Validation runner dry-run endpoint executed instead of listing commands")

        run_response = request(
            app,
            "POST",
            "/portal/validation-runner/run",
            json_payload={"command_ids": ["phase34_runner_self_check"], "collect_all": True},
        )
        if run_response.status_code != 200:
            errors.append(f"Validation runner run endpoint failed: {run_response.text}")
        else:
            run_payload = cast(dict[str, Any], run_response.json())
            validate_boundary_payload(run_payload, errors, "validation-runner/run")
            if run_payload.get("status") != "passed":
                errors.append("Validation runner run endpoint did not pass safe self-check")

        latest_response = request(app, "GET", "/portal/validation-runner/latest-report")
        latest_payload = cast(dict[str, Any], latest_response.json())
        if latest_payload.get("status") != "available":
            errors.append("Latest validation report endpoint did not expose the written report")

        rejected = request(
            app,
            "POST",
            "/portal/validation-runner/run",
            json_payload={"command_ids": ["python -c arbitrary shell text"]},
        )
        if rejected.status_code != 400:
            errors.append("Validation runner run endpoint accepted unapproved command text")

        schema_rejected = request(
            app,
            "POST",
            "/portal/validation-runner/run",
            json_payload={"command_ids": ["phase34_runner_self_check"], "shell": "true"},
        )
        if schema_rejected.status_code != 422:
            errors.append("Validation runner run endpoint accepted an extra shell field")


def validate_no_forbidden_routes(errors: list[str]) -> None:
    route_paths = {
        path
        for route in create_app().routes
        if isinstance(path := getattr(route, "path", None), str)
    }
    for forbidden in ["/deploy", "/merge", "/tag", "/push"]:
        if forbidden in route_paths:
            errors.append(f"Phase 35 API exposes forbidden route: {forbidden}")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 35 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    validate_api_endpoints(errors)
    validate_no_forbidden_routes(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 35 operator portal local web API validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
