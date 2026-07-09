from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI

from factory.operator_portal.local_web_api import create_app
from factory.operator_portal.operator_guides import (
    OPERATOR_GUIDE_SAFETY_BOUNDARIES,
    STATUS_TAXONOMY,
    build_operator_guide_index,
)
from factory.operator_portal.validation_runner import ValidationRunnerService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase38_portal_ux_polish_and_operator_guides_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase38/portal_ux_polish_and_operator_guides_prompt.md"
INDEX_PATH = PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html"
SCRIPT_PATH = PROJECT_ROOT / "factory/operator_portal/web_ui/static/app.js"
GUIDE_PATHS = [
    PROJECT_ROOT / "docs/phase38/local_operator_guide.md",
    PROJECT_ROOT / "docs/phase38/troubleshooting_guide.md",
    PROJECT_ROOT / "docs/phase38/portal_workflow_guide.md",
    PROJECT_ROOT / "docs/phase38/status_taxonomy.md",
]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase38"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def make_app(tmp_path: Path) -> FastAPI:
    runner = ValidationRunnerService(report_path=tmp_path / "phase38_validation_report.json")
    return create_app(project_root=PROJECT_ROOT, validation_runner=runner)


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


def test_phase38_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase38_portal_ux_polish_and_operator_guides.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_operator_guide_index_exposes_guides_taxonomy_and_expected_outputs() -> None:
    index = build_operator_guide_index(project_root=PROJECT_ROOT)
    assert index["status"] == "available"
    assert index["operator_boundaries"] == OPERATOR_GUIDE_SAFETY_BOUNDARIES
    assert set(index["status_taxonomy"]) == set(STATUS_TAXONOMY)
    assert {guide["id"] for guide in index["guides"]} == {
        "local_operator_guide",
        "troubleshooting_guide",
        "portal_workflow_guide",
        "status_taxonomy",
    }
    assert all(guide["exists"] for guide in index["guides"])
    assert all(command["expected_output"] for command in index["quick_start_commands"])


def test_guides_contain_quick_start_boundaries_and_expected_outputs() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in GUIDE_PATHS)
    for phrase in [
        "Quick Start",
        "Expected output",
        "certification_ready_not_certified",
        "No live",
        "mocked or simulated",
        "Do not create real credentials",
    ]:
        assert phrase in combined


def test_operator_guides_endpoint_is_local_and_actionable(tmp_path: Path) -> None:
    response = request(make_app(tmp_path), "GET", "/portal/operator-guides")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert payload["operator_message"] == "Operator guides and status taxonomy are available locally."
    assert payload["safety_boundaries"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )
    guide_payload = payload["payload"]
    assert guide_payload["operator_boundaries"] == OPERATOR_GUIDE_SAFETY_BOUNDARIES
    assert set(guide_payload["status_taxonomy"]) == set(STATUS_TAXONOMY)


def test_rejected_validation_command_returns_operator_message_and_next_steps(
    tmp_path: Path,
) -> None:
    response = request(
        make_app(tmp_path),
        "POST",
        "/portal/validation-runner/run",
        json_payload={"command_ids": ["python -c arbitrary shell text"]},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["status"] == "rejected"
    assert detail["operator_message"] == "Validation request rejected: use approved command IDs only."
    assert "next_steps" in detail
    assert detail["safety_boundaries"]["live_provider_calls_allowed"] is False


def test_latest_report_missing_response_explains_local_next_steps(tmp_path: Path) -> None:
    response = request(make_app(tmp_path), "GET", "/portal/validation-runner/latest-report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"
    assert payload["operator_message"] == "No latest validation report exists yet."
    assert payload["next_steps"]


def test_ui_exposes_operator_guides_and_structured_error_rendering() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "Operator Guides" in html
    assert "guide-list" in html
    assert 'data-action="refresh-guides"' in html
    assert "/portal/operator-guides" in script
    assert "operator_message" in script
    assert "next_steps" in script


def test_policy_and_lifecycle_artifacts_keep_boundaries_closed() -> None:
    artifacts = [
        load_json(POLICY_PATH),
        load_json(ARTIFACT_DIR / "operator_guides_manifest.json"),
        load_json(ARTIFACT_DIR / "portal_ux_polish_gate.json"),
        load_json(ARTIFACT_DIR / "portal_ux_polish_audit.json"),
        load_json(ARTIFACT_DIR / "status_taxonomy.json"),
    ]
    for artifact in artifacts:
        assert artifact["certification_boundary"] == "certification_ready_not_certified"
        assert artifact["official_certification_claimed"] is False
        assert artifact["official_certification_granted"] is False
        assert artifact["production_readiness_claimed"] is False
        assert artifact["live_provider_calls_allowed"] is False
        assert artifact["real_secrets_allowed"] is False
        assert artifact["deployment_allowed"] is False
        assert artifact["merge_allowed"] is False
        assert artifact["tag_allowed"] is False
        assert artifact["push_allowed"] is False
        assert artifact["external_ecosystem_integrations"] == "mocked_or_simulated_only"


def test_no_forbidden_routes_or_secret_material_are_exposed(tmp_path: Path) -> None:
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
    assert "BEGIN PRIVATE KEY" not in combined
    assert "client_secret" not in combined
    assert "api_key" not in combined


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
