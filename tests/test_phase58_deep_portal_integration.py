from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI

from factory.operator_portal.deep_portal_integration import APP_ID, REQUIRED_VIEWS, DeepPortalIntegration
from factory.operator_portal.local_web_api import create_app
from factory.operator_portal.web_ui.app import create_web_ui_app
from scripts.run_portal_requirements_driven_application_engineering import APPROVAL_TOKEN


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase53" / "failed_debit_requirements.md"


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://phase58.local") as client:
        return await client.request(method, path, json=json_payload)


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload))


def test_overview_exposes_required_deep_portal_views() -> None:
    overview = DeepPortalIntegration(project_root=ROOT).overview()

    assert overview["product_name"] == "UPI App Factory"
    assert overview["repository_id"] == "upi_app_factory"
    assert overview["profiles"]["compatibility_scaffold"]["available"] is True
    assert overview["profiles"]["deep_profile"]["profile_id"] == "local-deep-v1"
    assert overview["mock_boundaries"]["real_payment_calls"] == "disabled"
    assert overview["mock_boundaries"]["default_runtime_llm_calls"] == 0
    assert REQUIRED_VIEWS.issubset(set(overview["views"]))
    assert "POST /v1/disputes" in overview["views"]["api"]
    assert overview["views"]["depth_score"]["overall"] >= 80
    assert overview["views"]["test_counts"]["failed"] == 0


def test_compile_and_proposal_use_real_adapter_without_execution() -> None:
    app = create_app(project_root=ROOT)
    payload = {"requirements_path": FIXTURE.relative_to(ROOT).as_posix()}

    compiled = request(app, "POST", "/operator-portal/api/deep-engineering/compile", json_payload=payload)
    assert compiled.status_code == 200
    compiled_payload = compiled.json()
    assert compiled_payload["status"] == "compiled"
    assert compiled_payload["diagnostics"]["valid"] is True
    assert compiled_payload["traceability"]

    proposal = request(app, "POST", "/operator-portal/api/deep-engineering/proposal", json_payload=payload)
    assert proposal.status_code == 200
    proposal_payload = proposal.json()
    assert proposal_payload["status"] == "proposal_ready"
    assert proposal_payload["plan"]["status"] == "PORTAL_APPLICATION_ENGINEERING_PLAN_VALIDATED"
    assert proposal_payload["plan"]["engineering_profile"] == "local-deep-v1"
    assert proposal_payload["real_payment_calls"] == "disabled"
    assert proposal_payload["llm_calls"] == 0


def test_approved_deep_run_generates_source_and_evidence_through_adapter() -> None:
    app = create_app(project_root=ROOT)
    payload = {
        "requirements_path": FIXTURE.relative_to(ROOT).as_posix(),
        "approval_token": APPROVAL_TOKEN,
    }

    response = request(app, "POST", "/operator-portal/api/deep-engineering/approved-run", json_payload=payload)
    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "completed"
    assert result["result"]["composer_profile"] == "local-deep-v1"
    assert result["result"]["real_payment_calls"] == "disabled"
    assert result["result"]["llm_calls"] == 0
    generated_root = Path(result["source_root"])
    assert generated_root.name == APP_ID
    assert (generated_root / "evidence" / "generation_manifest.json").is_file()


def test_file_browsing_and_downloads_are_safe() -> None:
    app = create_app(project_root=ROOT)

    source = request(
        app,
        "GET",
        "/operator-portal/api/deep-engineering/source?path=docs/domain_state_machine.md",
    )
    assert source.status_code == 200
    assert "received" in source.json()["text"]

    traversal = request(app, "GET", "/operator-portal/api/deep-engineering/source?path=../pyproject.toml")
    assert traversal.status_code == 404

    source_zip = request(app, "GET", "/operator-portal/api/deep-engineering/download/source")
    evidence_zip = request(app, "GET", "/operator-portal/api/deep-engineering/download/evidence")
    assert source_zip.status_code == 200
    assert evidence_zip.status_code == 200
    assert source_zip.headers["content-disposition"] == 'attachment; filename="phase58_source.zip"'
    assert evidence_zip.headers["content-disposition"] == 'attachment; filename="phase58_evidence.zip"'
    assert len(source_zip.content) > 100
    assert len(evidence_zip.content) > 100


def test_server_rendered_ui_contains_deep_portal_content() -> None:
    app = create_web_ui_app(project_root=ROOT)

    response = request(app, "GET", "/operator-portal/deep-engineering")

    assert response.status_code == 200
    assert "UPI App Factory" in response.text
    assert "Deep application engineering portal" in response.text
    assert "State Machine" in response.text
    assert "Source Browser" in response.text
