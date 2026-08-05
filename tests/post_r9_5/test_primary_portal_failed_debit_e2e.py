from __future__ import annotations

from pathlib import Path
import shutil
import time
from typing import Any

from factory.application_engineering.portfolio import PortfolioCatalogue, PortfolioStore
from factory.operator_portal.browser_intake_orchestration import (
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _contained_test_root(tmp_path: Path, name: str) -> Path:
    root = PROJECT_ROOT / "workspace" / "factory_generated" / "post_r9_5" / tmp_path.name / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _requirements() -> str:
    return """# Primary portal failed-debit runtime

Build and register the authoritative local failed-debit runtime with evidence
collection, investigation, human review, disposition, audit verification,
closure, mock-only payment boundaries, and deterministic local test proof.
"""


def _wait(orchestrator: BrowserIntakeOrchestrator, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        run = orchestrator.get_run(run_id)
        if run["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return run
        time.sleep(0.1)
    raise AssertionError("browser-operated portal run did not become terminal")


def test_primary_portal_registers_and_proves_the_authoritative_failed_debit_runtime(
    tmp_path: Path,
) -> None:
    portfolio_root = _contained_test_root(tmp_path, "portfolio")
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "portal_runs",
        portfolio_state_root=portfolio_root,
    )

    created = orchestrator.create_run(_requirements())
    run_id = str(created["run_id"])
    orchestrator.plan(run_id)
    orchestrator.approve(run_id, actor="operator", approval_token=APPROVAL_TOKEN)
    orchestrator.execute(run_id)
    terminal = _wait(orchestrator, run_id)

    assert terminal["state"] == "SUCCEEDED"
    assert terminal["final_decision"] == "GO"

    result = terminal["engineering_result"]
    assert result["engineering_profile"] == "authoritative-failed-debit-v1"
    assert result["failed_debit_runtime_contract"] is True
    assert result["failed_debit_primary_flow_test"] is True
    assert result["primary_runtime_control_plane"] == "portfolio_authoritative"
    assert PRIMARY_TEST_PATH in result["generated_test_execution"]["tests_executed"]["all"]

    endpoints = {
        (item["method"], item["path"])
        for item in result["openapi_inventory"]["endpoint_inventory"]
    }
    assert ("POST", "/v1/disputes") in endpoints
    assert ("POST", "/v1/disputes/{dispute_id}/review-decisions") in endpoints
    assert ("GET", "/v1/disputes/{dispute_id}/audit-integrity") in endpoints
    assert ("POST", "/v1/disputes/{dispute_id}/close") in endpoints
    assert ("GET", "/v1/disputes/{dispute_id}/history") in endpoints

    registration = result["portfolio_registration"]
    version = PortfolioCatalogue(
        store=PortfolioStore(project_root=PROJECT_ROOT, state_root=portfolio_root)
    ).get(
        app_id=registration["app_id"],
        version_id=registration["version_id"],
    )
    assert version.entrypoint == f"app.{registration['app_id']}.interfaces.api.main:app"
    assert "failed_debit_disputes" in version.capabilities
    assert "audit_integrity" in version.capabilities
    assert "closure" in version.capabilities

    application_root = Path(registration["application_root"])
    assert (application_root / "app" / registration["app_id"] / "interfaces" / "api" / "main.py").is_file()
    assert (application_root / "generated_application" / "app" / "interfaces" / "api" / "main.py").is_file()


PRIMARY_TEST_PATH = "tests/test_failed_debit_primary_runtime.py"
