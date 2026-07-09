#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.web_ui import (  # noqa: E402
    WEB_UI_SAFETY_BOUNDARIES,
    create_web_ui_app,
    get_web_ui_manifest,
)
from factory.operator_portal.validation_runner import ValidationRunnerService  # noqa: E402


APP_ID = "upi_dispute_resolution"
UI_SERVICE_PATH = Path("factory/operator_portal/web_ui/app.py")
UI_ASSET_DIR = Path("factory/operator_portal/web_ui/static")
INDEX_PATH = UI_ASSET_DIR / "index.html"
SCRIPT_PATH = UI_ASSET_DIR / "app.js"
STYLE_PATH = UI_ASSET_DIR / "styles.css"
RUN_SCRIPT_PATH = Path("scripts/run_phase36_operator_portal_local_web_ui.py")
POLICY_PATH = Path("policies/phase36_operator_portal_local_web_ui_policy.json")
PROMPT_PATH = Path("prompts/phase36/operator_portal_local_web_ui_prompt.md")
TEST_PATH = Path("tests/test_phase36_operator_portal_local_web_ui.py")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase36"
)

REQUIRED_FILES = [
    UI_SERVICE_PATH,
    INDEX_PATH,
    SCRIPT_PATH,
    STYLE_PATH,
    RUN_SCRIPT_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    TEST_PATH,
    ARTIFACT_DIR / "operator_portal_local_web_ui_gate.json",
    ARTIFACT_DIR / "operator_portal_local_web_ui_audit.json",
    ARTIFACT_DIR / "operator_portal_local_web_ui_manifest.json",
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

REQUIRED_UI_MARKERS = [
    "health-card",
    "evidence-card",
    "download-card",
    "validation-dry-run-card",
    "validation-run-card",
    "latest-report-card",
    "boundary-list",
    "data-action=\"export-download\"",
    "data-action=\"validation-dry-run\"",
    "data-action=\"validation-run\"",
    "data-action=\"latest-report\"",
    "certification_ready_not_certified",
    "No official certification or official approval is claimed.",
    "scope is local-readiness only",
    "External ecosystem integrations remain mocked or simulated.",
]

FORBIDDEN_SOURCE_TERMS = [
    "shell=True",
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "git push",
    "git tag",
    "git merge",
    "api_key",
    "client_secret",
    "BEGIN PRIVATE KEY",
]

FORBIDDEN_ROUTE_PATHS = {"/deploy", "/merge", "/tag", "/push"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "operator_portal_local_web_ui_gate.json")
    audit = load_json(ARTIFACT_DIR / "operator_portal_local_web_ui_audit.json")
    artifact_manifest = load_json(ARTIFACT_DIR / "operator_portal_local_web_ui_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    index = INDEX_PATH.read_text(encoding="utf-8")
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    style = STYLE_PATH.read_text(encoding="utf-8")
    service_source = UI_SERVICE_PATH.read_text(encoding="utf-8")
    run_source = RUN_SCRIPT_PATH.read_text(encoding="utf-8")
    combined_source = "\n".join([index, script, style, service_source, run_source])

    if policy.get("mandatory_gate") != "PHASE36-OPERATOR-PORTAL-LOCAL-WEB-UI-GATE":
        errors.append("Phase 36 policy missing mandatory local web UI gate")
    if policy.get("ui_asset_directory") != str(UI_ASSET_DIR):
        errors.append("Phase 36 policy does not identify the UI asset directory")
    if policy.get("ui_service") != str(UI_SERVICE_PATH):
        errors.append("Phase 36 policy does not identify the UI service")
    if set(policy.get("api_endpoints_consumed", [])) != EXPECTED_ENDPOINTS:
        errors.append("Phase 36 policy endpoint set does not match the Phase 35 API")
    if policy.get("local_only") is not True:
        errors.append("Phase 36 policy does not mark the UI as local-only")
    if policy.get("local_readiness_scope") != "local_operator_portal_browser_ui_only":
        errors.append("Phase 36 policy does not scope readiness to local browser UI only")
    if policy.get("external_cdn_dependencies_allowed") is not False:
        errors.append("Phase 36 policy allows external CDN dependencies")
    if policy.get("arbitrary_command_execution_allowed") is not False:
        errors.append("Phase 36 policy allows arbitrary command execution")

    for artifact, name in [
        (policy, "policy"),
        (gate, "gate"),
        (audit, "audit"),
        (artifact_manifest, "manifest"),
    ]:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 36 {name} changed certification boundary")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 36 {name} claims official certification")
        if artifact.get("official_certification_granted") is not False:
            errors.append(f"Phase 36 {name} claims official certification grant")
        if artifact.get("production_readiness_claimed") is not False:
            errors.append(f"Phase 36 {name} claims production readiness")

    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
    ]:
        if policy.get(field) is not False:
            errors.append(f"Phase 36 policy has invalid safety field: {field}")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 36 policy does not keep ecosystem integrations mocked")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 36 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "local browser UI",
        "Phase 35 local API",
        "validation dry-run",
        "certification_ready_not_certified",
        "Do not fake success",
        "mocked or simulated",
        "Do not use external CDN assets",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 36 prompt missing required phrase: {phrase}")

    for marker in REQUIRED_UI_MARKERS:
        if marker not in index:
            errors.append(f"Phase 36 UI missing required marker: {marker}")
    for endpoint in [
        "/health",
        "/portal/evidence-dashboard",
        "/portal/download-center/status",
        "/portal/download-center/export",
        "/portal/validation-runner/dry-run",
        "/portal/validation-runner/run",
        "/portal/validation-runner/latest-report",
    ]:
        if endpoint not in script:
            errors.append(f"Phase 36 UI script does not consume endpoint: {endpoint}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in combined_source:
            errors.append(f"Phase 36 UI source includes forbidden term: {term}")
    external_urls = re.findall(r"https?://(?!local-operator-portal)[^\"]+", combined_source)
    if external_urls:
        errors.append(f"Phase 36 UI includes external URL dependencies: {external_urls}")


def validate_manifest(errors: list[str]) -> None:
    manifest = get_web_ui_manifest()
    if manifest.get("phase") != "phase36_operator_portal_local_web_ui":
        errors.append("Phase 36 UI manifest has an unexpected phase")
    if set(manifest.get("api_endpoints_consumed", [])) != EXPECTED_ENDPOINTS:
        errors.append("Phase 36 UI manifest endpoint set does not match expected endpoints")
    asset_paths = {
        asset.get("path")
        for asset in manifest.get("assets", [])
        if isinstance(asset, dict)
    }
    for path in [str(INDEX_PATH), str(SCRIPT_PATH), str(STYLE_PATH)]:
        if path not in asset_paths:
            errors.append(f"Phase 36 UI manifest missing asset: {path}")
    if manifest.get("safety_boundaries") != WEB_UI_SAFETY_BOUNDARIES:
        errors.append("Phase 36 UI manifest safety boundaries changed")


def validate_boundary_payload(payload: dict[str, Any], errors: list[str], context: str) -> None:
    boundaries = payload.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append(f"{context} does not expose safety boundaries")
        return
    safety = cast(dict[str, Any], boundaries)
    for key, expected in WEB_UI_SAFETY_BOUNDARIES.items():
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


def validate_served_ui(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmpdir:
        report_path = Path(tmpdir) / "phase36_validation_report.json"
        runner = ValidationRunnerService(report_path=report_path)
        app = create_web_ui_app(project_root=PROJECT_ROOT, validation_runner=runner)

        index_response = request(app, "GET", "/operator-ui/")
        if index_response.status_code != 200:
            errors.append(f"GET /operator-ui/ failed with {index_response.status_code}")
        elif "Operator Portal" not in index_response.text:
            errors.append("Served Phase 36 UI does not include operator portal title")

        script_response = request(app, "GET", "/operator-ui/app.js")
        if script_response.status_code != 200:
            errors.append(f"GET /operator-ui/app.js failed with {script_response.status_code}")
        elif "fetch(path" not in script_response.text:
            errors.append("Served Phase 36 UI script does not contain local fetch helper")

        manifest_response = request(app, "GET", "/portal/web-ui/manifest")
        if manifest_response.status_code != 200:
            errors.append(f"GET /portal/web-ui/manifest failed with {manifest_response.status_code}")
        else:
            validate_boundary_payload(
                cast(dict[str, Any], manifest_response.json()),
                errors,
                "portal/web-ui/manifest",
            )

        dry_run = request(app, "GET", "/portal/validation-runner/dry-run")
        if dry_run.status_code != 200:
            errors.append(f"Phase 36 served API dry-run failed with {dry_run.status_code}")
        else:
            dry_payload = cast(dict[str, Any], dry_run.json())
            report = cast(dict[str, Any], dry_payload.get("report", {}))
            if report.get("dry_run") is not True:
                errors.append("Phase 36 served UI/API dry-run executed commands")

        run_response = request(
            app,
            "POST",
            "/portal/validation-runner/run",
            json_payload={"command_ids": ["phase34_runner_self_check"], "collect_all": True},
        )
        if run_response.status_code != 200:
            errors.append(f"Phase 36 served validation run failed: {run_response.text}")
        else:
            run_payload = cast(dict[str, Any], run_response.json())
            if run_payload.get("status") != "passed":
                errors.append("Phase 36 served validation run did not pass safe self-check")

        rejected = request(
            app,
            "POST",
            "/portal/validation-runner/run",
            json_payload={"command_ids": ["python -c arbitrary shell text"]},
        )
        if rejected.status_code != 400:
            errors.append("Phase 36 served validation endpoint accepted arbitrary command text")


def validate_no_forbidden_routes(errors: list[str]) -> None:
    route_paths = {
        path
        for route in create_web_ui_app().routes
        if isinstance(path := getattr(route, "path", None), str)
    }
    for forbidden in FORBIDDEN_ROUTE_PATHS:
        if forbidden in route_paths:
            errors.append(f"Phase 36 UI app exposes forbidden route: {forbidden}")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 36 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    validate_manifest(errors)
    validate_served_ui(errors)
    validate_no_forbidden_routes(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 36 operator portal local web UI validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
