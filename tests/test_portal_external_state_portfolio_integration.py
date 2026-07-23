from __future__ import annotations

import json
from pathlib import Path
import shutil
import time
from typing import Any

import pytest

from factory.application_engineering.portfolio import PortfolioCatalogue, PortfolioError, PortfolioStore
from factory.operator_portal.browser_intake_orchestration import (
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _contained_test_root(tmp_path: Path, name: str) -> Path:
    root = PROJECT_ROOT / "workspace" / "factory_generated" / "portal_external_state_tests" / tmp_path.name / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _requirements() -> str:
    return """# Fictional UPI dispute application

Build a local mock-safe generated application with health, readiness,
idempotent dispute creation, deterministic evidence, generated tests and no
live payment provider calls.
"""


def _approved_run(orchestrator: BrowserIntakeOrchestrator) -> str:
    run = orchestrator.create_run(_requirements())
    run_id = str(run["run_id"])
    orchestrator.plan(run_id)
    orchestrator.approve(run_id, actor="operator", approval_token=APPROVAL_TOKEN)
    return run_id


def _wait(orchestrator: BrowserIntakeOrchestrator, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        run = orchestrator.get_run(run_id)
        if run["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not become terminal")


def test_external_xdg_browser_state_uses_worktree_portfolio_root(tmp_path: Path) -> None:
    browser_root = tmp_path / "xdg state" / "operator_portal_runs"
    portfolio_root = _contained_test_root(tmp_path, "portfolio")
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=browser_root,
        portfolio_state_root=portfolio_root,
    )
    run_id = _approved_run(orchestrator)
    orchestrator.execute(run_id)
    terminal = _wait(orchestrator, run_id)

    assert terminal["state"] == "SUCCEEDED"
    assert terminal["final_decision"] == "GO"
    result = terminal["engineering_result"]
    version_id = result["portfolio_registration"]["version_id"]
    versions = PortfolioCatalogue(
        store=PortfolioStore(project_root=PROJECT_ROOT, state_root=portfolio_root)
    ).catalogue()["versions"]
    assert any(
        item["app_id"] == "upi_dispute_resolution" and item["version_id"] == version_id
        for item in versions.values()
    )


def test_registration_failure_persists_failed_no_go(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "portal_runs",
        portfolio_state_root=_contained_test_root(tmp_path, "portfolio"),
    )
    run_id = _approved_run(orchestrator)

    def fail_register(*args: object, **kwargs: object) -> dict[str, object]:
        raise PortfolioError("fictional registration failure")

    monkeypatch.setattr(orchestrator, "_register_generated_application", fail_register)
    orchestrator.execute(run_id)
    terminal = _wait(orchestrator, run_id)

    assert terminal["state"] == "FAILED"
    assert terminal["final_decision"] == "NO-GO"
    assert terminal["engineering_result"]["registered"] is False
    events = (tmp_path / "portal_runs" / run_id / "events.jsonl").read_text(encoding="utf-8")
    assert "engineering_failed_closed" in events


def test_orphaned_non_terminal_recovery(tmp_path: Path) -> None:
    portfolio_root = _contained_test_root(tmp_path, "portfolio")
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "portal_runs",
        portfolio_state_root=portfolio_root,
    )
    run_id = _approved_run(orchestrator)
    paths = orchestrator._paths(run_id)
    state = json.loads(paths.state.read_text(encoding="utf-8"))
    state["state"] = "EXECUTING"
    paths.state.write_text(json.dumps(state), encoding="utf-8")

    recovered = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "portal_runs",
        portfolio_state_root=portfolio_root,
    )
    terminal = recovered.get_run(run_id)
    assert terminal["state"] == "FAILED"
    assert terminal["final_decision"] == "NO-GO"
