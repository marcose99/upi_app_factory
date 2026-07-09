from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI

from factory.operator_portal.web_ui import (
    WEB_UI_SAFETY_BOUNDARIES,
    create_web_ui_app,
    get_web_ui_manifest,
)
from factory.operator_portal.validation_runner import ValidationRunnerService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase36_operator_portal_local_web_ui_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase36/operator_portal_local_web_ui_prompt.md"
INDEX_PATH = PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html"
SCRIPT_PATH = PROJECT_ROOT / "factory/operator_portal/web_ui/static/app.js"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def make_app(tmp_path: Path | None = None) -> FastAPI:
    runner = None
    if tmp_path is not None:
        runner = ValidationRunnerService(report_path=tmp_path / "phase36_validation_report.json")
    return create_web_ui_app(project_root=PROJECT_ROOT, validation_runner=runner)


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-operator-portal") as client:
        return await client.request(method, path, json=json_payload)


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload))


def test_phase36_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase36_operator_portal_local_web_ui.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_static_ui_contains_required_operator_sections() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    for marker in [
        "health-card",
        "evidence-card",
        "download-card",
        "validation-dry-run-card",
        "validation-run-card",
        "latest-report-card",
        "boundary-list",
        "certification_ready_not_certified",
        "No official certification or official approval is claimed.",
        "scope is local-readiness only",
    ]:
        assert marker in html


def test_ui_script_consumes_phase35_api_endpoints() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    for endpoint in [
        "/health",
        "/portal/evidence-dashboard",
        "/portal/download-center/status",
        "/portal/download-center/export",
        "/portal/validation-runner/dry-run",
        "/portal/validation-runner/run",
        "/portal/validation-runner/latest-report",
    ]:
        assert endpoint in script
    assert "phase34_runner_self_check" in script
    assert "fetch(path" in script


def test_web_ui_app_serves_index_and_assets(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    index_response = request(app, "GET", "/operator-ui/")
    assert index_response.status_code == 200
    assert "Operator Portal" in index_response.text

    script_response = request(app, "GET", "/operator-ui/app.js")
    assert script_response.status_code == 200
    assert "/portal/validation-runner/run" in script_response.text

    redirect_response = request(app, "GET", "/")
    assert redirect_response.status_code in {200, 307}


def test_web_ui_manifest_exposes_local_boundaries() -> None:
    manifest = get_web_ui_manifest()
    assert manifest["phase"] == "phase36_operator_portal_local_web_ui"
    assert manifest["safety_boundaries"] == WEB_UI_SAFETY_BOUNDARIES
    asset_paths = {asset["path"] for asset in manifest["assets"]}
    assert "factory/operator_portal/web_ui/static/index.html" in asset_paths
    assert "factory/operator_portal/web_ui/static/app.js" in asset_paths
    assert "factory/operator_portal/web_ui/static/styles.css" in asset_paths


def test_web_ui_manifest_route_exposes_local_boundaries(tmp_path: Path) -> None:
    response = request(make_app(tmp_path), "GET", "/portal/web-ui/manifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["safety_boundaries"] == WEB_UI_SAFETY_BOUNDARIES


def test_ui_preserves_phase35_health_endpoint(tmp_path: Path) -> None:
    response = request(make_app(tmp_path), "GET", "/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["safety_boundaries"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )


def test_ui_validation_controls_use_allowlisted_command_only(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    dry_run = request(app, "GET", "/portal/validation-runner/dry-run")
    assert dry_run.status_code == 200
    assert dry_run.json()["report"]["dry_run"] is True

    run = request(
        app,
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["phase34_runner_self_check"], "collect_all": True},
    )
    assert run.status_code == 200
    assert run.json()["status"] == "passed"

    rejected = request(
        app,
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["python -c arbitrary shell text"]},
    )
    assert rejected.status_code == 400


def test_policy_preserves_governance_boundaries() -> None:
    policy = load_json(POLICY_PATH)
    assert policy["local_only"] is True
    assert policy["local_readiness_scope"] == "local_operator_portal_browser_ui_only"
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert policy["production_readiness_claimed"] is False
    assert policy["external_cdn_dependencies_allowed"] is False
    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
    ]:
        assert policy[field] is False
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"


def test_no_live_provider_secret_deploy_merge_tag_push_routes_are_exposed(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    route_paths = {
        path
        for route in app.routes
        if isinstance(path := getattr(route, "path", None), str)
    }
    assert "/deploy" not in route_paths
    assert "/merge" not in route_paths
    assert "/tag" not in route_paths
    assert "/push" not in route_paths

    combined = INDEX_PATH.read_text(encoding="utf-8") + SCRIPT_PATH.read_text(encoding="utf-8")
    assert "api_key" not in combined
    assert "client_secret" not in combined
    assert "BEGIN PRIVATE KEY" not in combined


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
