from __future__ import annotations

import json
import subprocess
import sys
import asyncio
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI

from factory.operator_portal.download_center import DownloadCenterService
from factory.operator_portal.local_web_api import LOCAL_API_SAFETY_BOUNDARIES, create_app
from factory.operator_portal.validation_runner import ValidationRunnerService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase35_operator_portal_local_web_api_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase35/operator_portal_local_web_api_prompt.md"


class StubDownloadCenter:
    def trigger_governed_export(self) -> dict[str, Any]:
        return {
            "status": "export_ready",
            "phase31_export_invoked": True,
            "bundle_metadata": {
                "app_id": "upi_dispute_resolution",
                "certification_boundary": "certification_ready_not_certified",
                "live_provider_calls_allowed": False,
                "real_secrets_allowed": False,
                "deployment_allowed": False,
                "external_ecosystem_integrations": "mocked_or_simulated_only",
            },
            "safety_boundaries": {
                "certification_boundary": "certification_ready_not_certified",
                "official_certification_claimed": False,
                "official_certification_granted": False,
                "production_readiness_claimed": False,
                "live_provider_calls_allowed": False,
                "real_secrets_allowed": False,
                "deployment_allowed": False,
                "external_ecosystem_integrations": "mocked_or_simulated_only",
            },
        }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def make_client(
    tmp_path: Path,
    *,
    download_center: DownloadCenterService | None = None,
) -> FastAPI:
    report_path = tmp_path / "phase35_validation_report.json"
    runner = ValidationRunnerService(report_path=report_path)
    return create_app(
        project_root=PROJECT_ROOT,
        download_center=download_center,
        validation_runner=runner,
    )


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


def assert_local_boundaries(payload: dict[str, Any]) -> None:
    assert payload["safety_boundaries"] == LOCAL_API_SAFETY_BOUNDARIES


def test_phase35_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase35_operator_portal_local_web_api.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_health_endpoint_is_local_only(tmp_path: Path) -> None:
    response = request(make_client(tmp_path), "GET", "/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["phase"] == "phase35_operator_portal_local_web_api"
    assert_local_boundaries(payload)


def test_evidence_dashboard_endpoint_exposes_existing_dashboard(tmp_path: Path) -> None:
    response = request(make_client(tmp_path), "GET", "/portal/evidence-dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["payload"]["app_id"] == "upi_dispute_resolution"
    assert payload["payload"]["phase_coverage"]["posture"] == (
        "certification_ready_not_certified"
    )
    assert_local_boundaries(payload)


def test_download_center_status_endpoint_is_read_only(tmp_path: Path) -> None:
    response = request(make_client(tmp_path), "GET", "/portal/download-center/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["download_center"]["service_path"] == (
        "factory/operator_portal/download_center.py"
    )
    assert payload["phase31_export_bundle_metadata"]["status"] in {
        "available",
        "partial",
        "missing",
    }
    assert_local_boundaries(payload)


def test_download_center_export_endpoint_wraps_governed_export(tmp_path: Path) -> None:
    app = make_client(
        tmp_path,
        download_center=cast(DownloadCenterService, StubDownloadCenter()),
    )
    response = request(app, "POST", "/portal/download-center/export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "export_ready"
    assert payload["export"]["phase31_export_invoked"] is True
    assert_local_boundaries(payload)


def test_validation_runner_dry_run_lists_approved_commands(tmp_path: Path) -> None:
    response = request(make_client(tmp_path), "GET", "/portal/validation-runner/dry-run")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dry_run"
    report = payload["report"]
    assert report["dry_run"] is True
    assert report["command_results"]
    assert all("return_code" not in entry for entry in report["command_results"])
    assert_local_boundaries(payload)


def test_validation_runner_run_executes_only_allowlisted_command(tmp_path: Path) -> None:
    app = make_client(tmp_path)
    response = request(
        app,
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["phase34_runner_self_check"], "collect_all": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "passed"
    assert payload["report"]["command_results"][0]["command_id"] == (
        "phase34_runner_self_check"
    )
    assert payload["report"]["command_results"][0]["return_code"] == 0
    assert_local_boundaries(payload)


def test_validation_runner_rejects_arbitrary_command_text(tmp_path: Path) -> None:
    response = request(
        make_client(tmp_path),
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["python -c arbitrary shell text"]},
    )
    assert response.status_code == 400


def test_validation_runner_rejects_extra_shell_fields(tmp_path: Path) -> None:
    response = request(
        make_client(tmp_path),
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["phase34_runner_self_check"], "shell": "true"},
    )
    assert response.status_code == 422


def test_latest_report_reports_missing_then_available(tmp_path: Path) -> None:
    app = make_client(tmp_path)
    missing = request(app, "GET", "/portal/validation-runner/latest-report")
    assert missing.status_code == 200
    assert missing.json()["status"] == "missing"

    run_response = request(
        app,
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["phase34_runner_self_check"]},
    )
    assert run_response.status_code == 200

    available = request(app, "GET", "/portal/validation-runner/latest-report")
    assert available.status_code == 200
    payload = available.json()
    assert payload["status"] == "available"
    assert payload["report"]["status"] == "passed"
    assert_local_boundaries(payload)


def test_no_deploy_merge_tag_push_routes_are_exposed(tmp_path: Path) -> None:
    app = make_client(tmp_path)
    route_paths = {
        path
        for route in app.routes
        if isinstance(path := getattr(route, "path", None), str)
    }
    assert "/deploy" not in route_paths
    assert "/merge" not in route_paths
    assert "/tag" not in route_paths
    assert "/push" not in route_paths


def test_policy_preserves_governance_boundaries() -> None:
    policy = load_json(POLICY_PATH)
    assert policy["local_only"] is True
    assert policy["local_readiness_scope"] == "local_operator_portal_api_only"
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert policy["production_readiness_claimed"] is False
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


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
