from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from factory.application_engineering.portfolio import PortfolioCatalogue, PortfolioStore
from factory.operator_portal.portfolio_api import PortfolioAPI, PortfolioReadRequest, PortfolioVersionRequest
from scripts import run_portal_requirements_driven_application_engineering as adapter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _requirements(tmp_path: Path) -> Path:
    path = tmp_path / "requirements.md"
    path.write_text(
        """# Local mock-safe UPI dispute API

Build a deterministic local UPI dispute resolution API with health, readiness,
idempotent dispute creation, mock-only scenario endpoints, generated tests,
OpenAPI publication evidence, runtime observability metadata, and no live bank,
NPCI, PSP, provider, or payment-switch calls.
""",
        encoding="utf-8",
    )
    return path


def _config(tmp_path: Path, *, app_id: str = "upi_portal_evidence_test") -> adapter.AdapterConfig:
    return adapter.AdapterConfig(
        requirements=_requirements(tmp_path),
        app_id=app_id,
        output_root=tmp_path / "generated_application",
        evidence_root=tmp_path / "engineering_evidence",
        approval_mode="human-gated",
        approval_token=adapter.APPROVAL_TOKEN,
        mock_safe=True,
        plan_only=False,
        replace_existing=False,
        factory_root=PROJECT_ROOT,
        workspace_root=tmp_path,
        portfolio_state_root=tmp_path / "portfolio",
        register_with_portfolio=True,
    )


def test_generated_tests_execute_before_go_and_openapi_is_registered(tmp_path: Path) -> None:
    result = cast(dict[str, Any], adapter.run(_config(tmp_path)))

    assert result["status"] == adapter.SUCCESS_STATUS
    assert result["generated_test_execution"]["exit_code"] == 0
    assert result["generated_test_execution"]["go_gate"] == "GO"
    assert result["generated_test_execution"]["counts"]["collected"] >= 2
    assert result["tests_present"]["api"] == ["tests/test_api_contract.py"]
    assert result["tests_executed"]["api"] == ["tests/test_api_contract.py"]
    assert result["tests_present"]["ui"] == []
    assert result["tests_executed"]["ui"] == []
    assert result["openapi_inventory"]["catalogue_only_fallback_used"] is False
    assert {"method": "GET", "path": "/health"} in result["openapi_inventory"]["endpoint_inventory"]

    application_root = Path(str(result["application_root"]))
    assert (application_root / "docs" / "openapi.json").is_file()
    assert (application_root / "evidence" / "generated_test_execution.json").is_file()

    version_id = str(result["portfolio_registration"]["version_id"])
    catalogue = PortfolioCatalogue(
        store=PortfolioStore(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    ).catalogue()
    versions = cast(dict[str, Any], catalogue["versions"])
    version = cast(dict[str, Any], versions[f"upi_portal_evidence_test:{version_id}"])
    assert version["manifest"]["openapi"]["paths"]
    assert version["manifest"]["openapi_inventory"]["openapi_sha256"] == result["openapi_inventory"]["openapi_sha256"]

    api_payload = PortfolioAPI(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio").openapi_document(
        PortfolioVersionRequest(app_id="upi_portal_evidence_test", version_id=version_id)
    )
    assert api_payload["status"] == "available"
    assert "/health" in api_payload["endpoint_inventory"]

    portfolio_api = PortfolioAPI(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    runtime_request = PortfolioReadRequest(
        app_id="upi_portal_evidence_test",
        version_id=version_id,
        run_id="portfolio_logs_metrics_test",
        port=18042,
    )
    metrics = portfolio_api.metrics(runtime_request)
    logs = portfolio_api.logs(runtime_request)
    assert metrics["app_id"] == "upi_portal_evidence_test"
    assert metrics["version_id"] == version_id
    assert metrics["requirements_sha256"] == result["requirements_sha256"]
    assert metrics["real_payment_calls"] == "disabled"
    assert metrics["default_runtime_llm_calls"] == 0
    assert logs["status"] == "missing"
    assert logs["version_identity_sha256"] == metrics["version_identity_sha256"]


def test_generated_test_failure_fails_closed_before_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def injected_failure(**_: object) -> dict[str, object]:
        return {
            "schema_version": "generated-application-test-execution.v1",
            "app_id": "upi_portal_evidence_test",
            "version_id": "v1_injected",
            "run_id": "portal_injected",
            "requirements_sha256": "0" * 64,
            "argv": ["python", "-m", "pytest", "-q", "tests"],
            "exit_code": 1,
            "counts": {"collected": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0, "warnings": 0},
            "tests_present": {"api": ["tests/test_api_contract.py"], "ui": [], "other": ["tests/test_service.py"], "all": ["tests/test_api_contract.py", "tests/test_service.py"], "count": 2},
            "tests_executed": {"api": [], "ui": [], "other": [], "all": [], "count": 0},
            "output_sha256": "1" * 64,
            "redacted_output": "1 failed, 1 passed",
            "go_gate": "NO-GO",
            "fail_closed": True,
        }

    monkeypatch.setattr(adapter, "_execute_generated_tests", injected_failure)

    with pytest.raises(adapter.AdapterError, match="generated application tests failed"):
        adapter.run(_config(tmp_path))

    assert not (tmp_path / "generated_application").exists()
    evidence_reports = sorted((tmp_path / "engineering_evidence").glob("*/generated_test_execution.json"))
    assert evidence_reports
    report = json.loads(evidence_reports[-1].read_text(encoding="utf-8"))
    assert report["exit_code"] == 1
    assert report["go_gate"] == "NO-GO"
    assert PortfolioCatalogue(
        store=PortfolioStore(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    ).catalogue()["versions"] == {}
