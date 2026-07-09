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

from factory.operator_portal.local_web_api import create_app  # noqa: E402
from factory.operator_portal.operator_guides import (  # noqa: E402
    OPERATOR_GUIDE_SAFETY_BOUNDARIES,
    STATUS_TAXONOMY,
    build_operator_guide_index,
)
from factory.operator_portal.validation_runner import ValidationRunnerService  # noqa: E402


APP_ID = "upi_dispute_resolution"
PHASE = "phase38_portal_ux_polish_and_operator_guides"
SERVICE_PATH = Path("factory/operator_portal/operator_guides.py")
API_PATH = Path("factory/operator_portal/local_web_api.py")
INDEX_PATH = Path("factory/operator_portal/web_ui/static/index.html")
SCRIPT_PATH = Path("factory/operator_portal/web_ui/static/app.js")
STYLE_PATH = Path("factory/operator_portal/web_ui/static/styles.css")
POLICY_PATH = Path("policies/phase38_portal_ux_polish_and_operator_guides_policy.json")
PROMPT_PATH = Path("prompts/phase38/portal_ux_polish_and_operator_guides_prompt.md")
TEST_PATH = Path("tests/test_phase38_portal_ux_polish_and_operator_guides.py")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase38"
)

GUIDE_PATHS = [
    Path("docs/phase38/local_operator_guide.md"),
    Path("docs/phase38/troubleshooting_guide.md"),
    Path("docs/phase38/portal_workflow_guide.md"),
    Path("docs/phase38/status_taxonomy.md"),
]

REQUIRED_FILES = [
    SERVICE_PATH,
    API_PATH,
    INDEX_PATH,
    SCRIPT_PATH,
    STYLE_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    TEST_PATH,
    *GUIDE_PATHS,
    ARTIFACT_DIR / "operator_guides_manifest.json",
    ARTIFACT_DIR / "portal_ux_polish_gate.json",
    ARTIFACT_DIR / "portal_ux_polish_audit.json",
    ARTIFACT_DIR / "status_taxonomy.json",
    ARTIFACT_DIR / "quick_start_expected_outputs.md",
]

REQUIRED_BOUNDARY_FIELDS = [
    "official_certification_claimed",
    "official_certification_granted",
    "production_readiness_claimed",
    "live_provider_calls_allowed",
    "real_secrets_allowed",
    "deployment_allowed",
    "merge_allowed",
    "tag_allowed",
    "push_allowed",
]

FORBIDDEN_SOURCE_TERMS = [
    "shell=True",
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "BEGIN PRIVATE KEY",
    "client_secret",
    "api_key",
    "git push",
    "git tag",
    "git merge",
]

FORBIDDEN_ROUTE_PATHS = {"/deploy", "/merge", "/tag", "/push"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_boundary_artifact(
    artifact: dict[str, Any],
    errors: list[str],
    context: str,
) -> None:
    if artifact.get("certification_boundary") != "certification_ready_not_certified":
        errors.append(f"{context} changed certification boundary")
    for field in REQUIRED_BOUNDARY_FIELDS:
        if artifact.get(field) is not False:
            errors.append(f"{context} has invalid boundary field: {field}")
    if artifact.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append(f"{context} does not keep ecosystem integrations mocked")
    scope = artifact.get("local_readiness_scope")
    if scope != "local_operator_guides_and_portal_workflows_only":
        errors.append(f"{context} does not scope readiness to local operator workflows")


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    manifest = load_json(ARTIFACT_DIR / "operator_guides_manifest.json")
    gate = load_json(ARTIFACT_DIR / "portal_ux_polish_gate.json")
    audit = load_json(ARTIFACT_DIR / "portal_ux_polish_audit.json")
    taxonomy = load_json(ARTIFACT_DIR / "status_taxonomy.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    guide_text = "\n".join(path.read_text(encoding="utf-8") for path in GUIDE_PATHS)
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [SERVICE_PATH, API_PATH, INDEX_PATH, SCRIPT_PATH, STYLE_PATH]
    )

    if policy.get("mandatory_gate") != "PHASE38-PORTAL-UX-POLISH-AND-OPERATOR-GUIDES-GATE":
        errors.append("Phase 38 policy missing mandatory gate")
    if policy.get("guide_service") != str(SERVICE_PATH):
        errors.append("Phase 38 policy does not identify the guide service")
    if policy.get("portal_guides_endpoint") != "GET /portal/operator-guides":
        errors.append("Phase 38 policy does not identify the guide endpoint")
    if policy.get("arbitrary_command_execution_allowed") is not False:
        errors.append("Phase 38 policy allows arbitrary command execution")

    for artifact, name in [
        (policy, "policy"),
        (manifest, "manifest"),
        (gate, "gate"),
        (audit, "audit"),
        (taxonomy, "taxonomy"),
    ]:
        validate_boundary_artifact(artifact, errors, f"Phase 38 {name}")

    expected_guides = {path.as_posix() for path in GUIDE_PATHS}
    if set(policy.get("required_guides", [])) != expected_guides:
        errors.append("Phase 38 policy guide list does not match required guides")
    if set(policy.get("required_status_vocabulary", [])) != set(STATUS_TAXONOMY):
        errors.append("Phase 38 policy status vocabulary does not match service taxonomy")
    artifact_taxonomy = taxonomy.get("status_taxonomy")
    if not isinstance(artifact_taxonomy, dict) or set(artifact_taxonomy) != set(STATUS_TAXONOMY):
        errors.append("Phase 38 lifecycle status taxonomy is incomplete")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 38 prompt does not inherit contract: {contract_path}")

    for phrase in [
        "certification_ready_not_certified",
        "Do not fake success",
        "mocked or simulated",
        "No live provider calls",
        "No real credentials",
        "No deployment, merge, tag, or push",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 38 prompt missing required phrase: {phrase}")

    for phrase in [
        "Quick Start",
        "Expected output",
        "Status Taxonomy",
        "Troubleshooting Guide",
        "Portal Workflow Guide",
        "certification_ready_not_certified",
        "mocked or simulated",
    ]:
        if phrase not in guide_text:
            errors.append(f"Phase 38 guides missing required phrase: {phrase}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source_text:
            errors.append(f"Phase 38 portal source includes forbidden term: {term}")
    external_urls = re.findall(r"https?://(?!local-operator-portal)[^\"]+", source_text)
    if external_urls:
        errors.append(f"Phase 38 portal source includes external URL dependencies: {external_urls}")

    for marker in [
        "Operator Guides",
        "guide-list",
        "data-action=\"refresh-guides\"",
        "/portal/operator-guides",
        "operator_message",
        "next_steps",
    ]:
        if marker not in source_text:
            errors.append(f"Phase 38 portal UX missing marker: {marker}")


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


def validate_endpoint_behavior(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmpdir:
        runner = ValidationRunnerService(report_path=Path(tmpdir) / "phase38_report.json")
        app = create_app(project_root=PROJECT_ROOT, validation_runner=runner)

        guides_response = request(app, "GET", "/portal/operator-guides")
        if guides_response.status_code != 200:
            errors.append(f"Operator guides endpoint failed: {guides_response.status_code}")
        else:
            payload = cast(dict[str, Any], guides_response.json())
            guide_payload = cast(dict[str, Any], payload.get("payload", {}))
            if payload.get("operator_message") != "Operator guides and status taxonomy are available locally.":
                errors.append("Operator guides endpoint missing operator message")
            if guide_payload.get("status") != "available":
                errors.append("Operator guides endpoint did not report available guides")
            if set(cast(dict[str, Any], guide_payload.get("status_taxonomy", {}))) != set(
                STATUS_TAXONOMY,
            ):
                errors.append("Operator guides endpoint taxonomy is incomplete")
            if guide_payload.get("operator_boundaries") != OPERATOR_GUIDE_SAFETY_BOUNDARIES:
                errors.append("Operator guides endpoint changed safety boundaries")

        rejected = request(
            app,
            "POST",
            "/portal/validation-runner/run",
            json_payload={"command_ids": ["python -c arbitrary shell text"]},
        )
        if rejected.status_code != 400:
            errors.append("Validation endpoint accepted arbitrary command text")
        else:
            detail = cast(dict[str, Any], rejected.json().get("detail", {}))
            if detail.get("operator_message") != (
                "Validation request rejected: use approved command IDs only."
            ):
                errors.append("Rejected validation response lacks clear operator message")
            if not detail.get("next_steps"):
                errors.append("Rejected validation response lacks next steps")


def validate_service_index(errors: list[str]) -> None:
    index = build_operator_guide_index(project_root=PROJECT_ROOT)
    if index.get("phase") != PHASE:
        errors.append("Operator guide index has unexpected phase")
    if index.get("status") != "available":
        errors.append("Operator guide index did not find all guide files")
    if index.get("operator_boundaries") != OPERATOR_GUIDE_SAFETY_BOUNDARIES:
        errors.append("Operator guide index changed safety boundaries")
    commands = index.get("quick_start_commands")
    if not isinstance(commands, list) or len(commands) < 3:
        errors.append("Operator guide index does not expose quick-start commands")
    for entry in cast(list[dict[str, Any]], commands if isinstance(commands, list) else []):
        if not entry.get("expected_output"):
            errors.append("Quick-start command missing expected output")


def validate_no_forbidden_routes(errors: list[str]) -> None:
    route_paths = {
        path
        for route in create_app().routes
        if isinstance(path := getattr(route, "path", None), str)
    }
    for forbidden in FORBIDDEN_ROUTE_PATHS:
        if forbidden in route_paths:
            errors.append(f"Phase 38 API exposes forbidden route: {forbidden}")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 38 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    validate_service_index(errors)
    validate_endpoint_behavior(errors)
    validate_no_forbidden_routes(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 38 portal UX polish and operator guides validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
