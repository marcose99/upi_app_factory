from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any
import zipfile

import pytest

from factory.application_engineering.portfolio import PortfolioCatalogue, PortfolioError, PortfolioStore
from factory.operator_portal.browser_intake_orchestration import (
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
)
from factory.operator_portal.portfolio_api import PortfolioAPI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_failed_debit_no_credit"
REQUIREMENTS_TEXT = (
    "# Synthetic UPI failed debit requirement\n\n"
    "Build a mock-only failed debit no credit dispute workflow with no live "
    "payment calls, no real customer data, and certification-ready-not-certified "
    "evidence boundaries.\n"
)
REQUIREMENTS_SHA256 = hashlib.sha256(REQUIREMENTS_TEXT.encode("utf-8")).hexdigest()


def _requirements() -> str:
    payload = REQUIREMENTS_TEXT.encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == REQUIREMENTS_SHA256
    return payload.decode("utf-8")


def _external_browser_root(tmp_path: Path) -> Path:
    candidates = [
        Path(value).expanduser()
        for value in [os.getenv("UPI_APP_FACTORY_TEST_EXTERNAL_STATE_ROOT")]
        if value
    ]
    candidates.extend(
        [
            Path("/dev/shm") / "upi_app_factory_portal_identity_tests",
            Path.home() / ".local" / "state" / "upi_app_factory_portal_identity_tests",
        ]
    )
    for candidate in candidates:
        root = (candidate / tmp_path.name).resolve()
        if root.is_relative_to(PROJECT_ROOT) or root.is_relative_to(Path("/tmp")):
            continue
        if root.exists():
            shutil.rmtree(root)
        try:
            root.mkdir(parents=True)
        except OSError:
            continue
        shutil.rmtree(root)
        return root
    raise AssertionError("no writable external browser state root outside project root and /tmp")


def _contained_test_root(tmp_path: Path, name: str) -> Path:
    return PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "identity_test_roots" / tmp_path.name / name


def _wait(orchestrator: BrowserIntakeOrchestrator, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        run = orchestrator.get_run(run_id)
        if run["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not reach a terminal state")


def _assert_zip_safe(content: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        assert names
        assert len(names) == len(set(names))
        assert all(not name.startswith("/") for name in names)
        assert all(".." not in Path(name).parts for name in names)
        assert all(info.external_attr >> 16 & 0o170000 != 0o120000 for info in archive.infolist())
        return names


def test_failed_debit_app_id_publication_catalogue_and_downloads(tmp_path: Path) -> None:
    browser_root = _external_browser_root(tmp_path)
    portfolio_root = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "phase51_identity_test_portfolio"
    if portfolio_root.exists():
        shutil.rmtree(portfolio_root)
    try:
        orchestrator = BrowserIntakeOrchestrator(
            project_root=PROJECT_ROOT,
            state_root=browser_root,
            portfolio_state_root=portfolio_root,
        )
        run = orchestrator.create_run(_requirements(), app_id=APP_ID)
        run_id = str(run["run_id"])

        assert browser_root.is_dir()
        assert not browser_root.is_relative_to(PROJECT_ROOT)
        assert not browser_root.is_relative_to(Path("/tmp"))
        assert portfolio_root.is_relative_to(PROJECT_ROOT)
        assert run["app_id"] == APP_ID
        assert run["requirements_sha256"] == REQUIREMENTS_SHA256

        plan_response = orchestrator.plan(run_id)
        plan = plan_response["run"]["plan"]
        assert plan["app_id"] == APP_ID
        assert plan["requirements_sha256"] == REQUIREMENTS_SHA256
        assert plan["plan"]["app_id"] == APP_ID
        assert Path(plan["plan"]["output_root"]).is_relative_to(PROJECT_ROOT)
        assert not (browser_root / run_id / "generated_application").exists()

        approval = orchestrator.approve(run_id, actor="operator", approval_token=APPROVAL_TOKEN)
        assert approval["run"]["approval"]["app_id"] == APP_ID

        first_execute = orchestrator.execute(run_id)
        second_execute = orchestrator.execute(run_id)
        assert first_execute["status"] in {"queued", "already_queued"}
        assert second_execute["status"] in {"already_queued", "already_succeeded"}

        terminal = _wait(orchestrator, run_id)
        assert terminal["state"] == "SUCCEEDED"
        assert terminal["final_decision"] == "GO"
        validation = orchestrator.validation(run_id)
        assert validation["mandatory_gates_passed"] is True
        assert validation["decision"] == "GO"

        result = terminal["engineering_result"]
        registration = result["portfolio_registration"]
        version_id = registration["version_id"]
        assert result["app_id"] == APP_ID
        assert result["requirements_sha256"] == REQUIREMENTS_SHA256
        assert registration["app_id"] == APP_ID
        assert registration["source_run_id"] == run_id
        assert registration["application_root"].startswith(str(PROJECT_ROOT))
        application_root = Path(registration["application_root"])
        assert application_root.is_dir()
        assert application_root.is_relative_to(PROJECT_ROOT)
        assert (application_root / "app" / APP_ID / "interfaces" / "api" / "main.py").is_file()

        catalogue = PortfolioCatalogue(
            store=PortfolioStore(project_root=PROJECT_ROOT, state_root=portfolio_root)
        ).catalogue()
        versions = catalogue["versions"]
        assert list(versions) == [f"{APP_ID}:{version_id}"]
        catalogue_record = versions[f"{APP_ID}:{version_id}"]
        assert catalogue_record["app_id"] == APP_ID
        assert catalogue_record["version_id"] == version_id
        assert catalogue_record["generated_run_id"] == run_id
        assert catalogue_record["manifest"]["app_id"] == APP_ID
        assert catalogue_record["manifest"]["version_id"] == version_id

        api_catalogue = PortfolioAPI(project_root=PROJECT_ROOT, state_root=portfolio_root).catalogue_payload()
        assert api_catalogue["catalogue"]["catalogue_sha256"] == catalogue["catalogue_sha256"]
        assert api_catalogue["versions"][0]["app_id"] == APP_ID

        post_terminal_execute = orchestrator.execute(run_id)
        assert post_terminal_execute["status"] == "already_succeeded"
        assert len(PortfolioCatalogue(store=PortfolioStore(project_root=PROJECT_ROOT, state_root=portfolio_root)).list_versions()) == 1

        application_archive = orchestrator.application_archive(run_id)
        evidence_archive = orchestrator.evidence_archive(run_id)
        app_names = _assert_zip_safe(application_archive.read_bytes())
        evidence_names = _assert_zip_safe(evidence_archive.read_bytes())
        assert f"generated_application/app/{APP_ID}/interfaces/api/main.py" in app_names
        assert f"{run_id}_evidence/requirements.md" in evidence_names
        with zipfile.ZipFile(application_archive) as archive:
            manifest = json.loads(archive.read("generated_application/generation_manifest.json"))
        assert manifest["app_id"] == APP_ID
        assert manifest["version_id"] == version_id
        assert manifest["requirements_sha256"] == REQUIREMENTS_SHA256
        assert manifest["portfolio_registration"]["generated_run_id"] == run_id
    finally:
        if browser_root.exists():
            shutil.rmtree(browser_root)
        if portfolio_root.exists():
            shutil.rmtree(portfolio_root)


def test_portfolio_error_fails_no_go_without_catalogue_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    browser_root = tmp_path / "runs"
    portfolio_root = _contained_test_root(tmp_path, "portfolio")
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=browser_root,
        portfolio_state_root=portfolio_root,
    )
    run = orchestrator.create_run(_requirements(), app_id=APP_ID)
    run_id = str(run["run_id"])
    orchestrator.plan(run_id)
    orchestrator.approve(run_id, actor="operator", approval_token=APPROVAL_TOKEN)

    def fail_register(*args: object, **kwargs: object) -> dict[str, object]:
        raise PortfolioError("injected registration failure")

    monkeypatch.setattr(orchestrator, "_register_generated_application", fail_register)
    orchestrator.execute(run_id)
    terminal = _wait(orchestrator, run_id)

    assert terminal["state"] == "FAILED"
    assert terminal["final_decision"] == "NO-GO"
    assert terminal["engineering_result"]["registered"] is False
    catalogue = PortfolioCatalogue(
        store=PortfolioStore(project_root=PROJECT_ROOT, state_root=portfolio_root)
    ).catalogue()
    assert catalogue["versions"] == {}
