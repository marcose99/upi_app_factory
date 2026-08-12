from __future__ import annotations

from pathlib import Path
import shutil
import threading
import time
from typing import Any

from factory.application_engineering.portfolio import PortfolioCatalogue, PortfolioStore
from factory.operator_portal.browser_intake_orchestration import (
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


ASYNC_ENGINEERING_TEST_TIMEOUT_SECONDS = 60.0
ASYNC_ENGINEERING_WORKER_CLEANUP_TIMEOUT_SECONDS = 5.0
ASYNC_ENGINEERING_POLL_INTERVAL_SECONDS = 0.05
TERMINAL_RUN_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


def _active_engineering_worker_names(run_id: str) -> list[str]:
    expected_name = f"portal-engineering-{run_id}"
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.is_alive() and thread.name == expected_name
    ]


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
    deadline = time.monotonic() + ASYNC_ENGINEERING_TEST_TIMEOUT_SECONDS
    run = orchestrator.get_run(run_id)
    while run.get("state") not in TERMINAL_RUN_STATES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(ASYNC_ENGINEERING_POLL_INTERVAL_SECONDS, remaining))
        run = orchestrator.get_run(run_id)
    if run.get("state") not in TERMINAL_RUN_STATES:
        raise AssertionError(
            "browser-operated portal run did not become terminal within "
            f"{ASYNC_ENGINEERING_TEST_TIMEOUT_SECONDS:.1f}s; run_id={run_id!r}; "
            f"state={run.get('state')!r}; "
            f"final_decision={run.get('final_decision')!r}; "
            f"error={run.get('error')!r}; "
            f"recent_events={run.get('events', [])[-5:]!r}"
        )

    cleanup_deadline = (
        time.monotonic() + ASYNC_ENGINEERING_WORKER_CLEANUP_TIMEOUT_SECONDS
    )
    active_workers = _active_engineering_worker_names(run_id)
    while active_workers and time.monotonic() < cleanup_deadline:
        time.sleep(ASYNC_ENGINEERING_POLL_INTERVAL_SECONDS)
        active_workers = _active_engineering_worker_names(run_id)
    if active_workers:
        raise AssertionError(
            "application-engineering worker did not stop after terminal state; "
            f"run_id={run_id!r}; state={run.get('state')!r}; "
            f"active_workers={active_workers!r}"
        )
    return run


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
