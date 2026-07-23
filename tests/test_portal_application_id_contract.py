from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.application_engineering.portfolio import PortfolioError, PortfolioStore
from factory.operator_portal.browser_intake_orchestration import (
    APP_ID,
    APPROVAL_TOKEN,
    BrowserIntakeOrchestrator,
    OrchestrationConflict,
    OrchestrationValidationError,
)
from scripts.run_portal_requirements_driven_application_engineering import (
    AdapterConfig,
    AdapterError,
    _source_commit,
    validate_app_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_PATH = Path(
    "/home/marcose/Downloads/01_upi_failed_debit_no_credit.md"
)


def _contained_test_root(tmp_path: Path, name: str) -> Path:
    return PROJECT_ROOT / "workspace" / "factory_generated" / "portal_app_id_contract_tests" / tmp_path.name / name


def _requirements() -> str:
    return REQUIREMENTS_PATH.read_text(encoding="utf-8")


def test_app_id_validation_rejects_unsafe_values() -> None:
    for value in [
        "../escape",
        "upi.failed",
        "upi-failed",
        "UPI_FAILED",
        "upi failed",
        "upi_failed;",
        "upi_failed/no_credit",
        "upi_failed\\no_credit",
        "upi_failed_न",
        ".",
    ]:
        with pytest.raises(AdapterError):
            validate_app_id(value)

    assert validate_app_id("upi_failed_debit_no_credit") == "upi_failed_debit_no_credit"


def test_unsafe_app_id_fails_before_run_creation(tmp_path: Path) -> None:
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "runs",
        portfolio_state_root=_contained_test_root(tmp_path, "portfolio"),
    )
    with pytest.raises(OrchestrationValidationError):
        orchestrator.create_run(_requirements(), app_id="../escape")
    assert not list((tmp_path / "runs").glob("run_*"))


def test_default_app_id_compatibility_is_persisted(tmp_path: Path) -> None:
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "runs",
        portfolio_state_root=_contained_test_root(tmp_path, "portfolio"),
    )
    run = orchestrator.create_run(_requirements())
    assert run["app_id"] == APP_ID
    state = json.loads((tmp_path / "runs" / run["run_id"] / "state.json").read_text(encoding="utf-8"))
    assert state["app_id"] == APP_ID
    assert state["app_id_sha256"]


def test_app_id_is_immutable_and_approval_bound(tmp_path: Path) -> None:
    orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "runs",
        portfolio_state_root=_contained_test_root(tmp_path, "portfolio"),
    )
    run = orchestrator.create_run(_requirements(), app_id="upi_failed_debit_no_credit")
    run_id = str(run["run_id"])
    orchestrator.plan(run_id)
    orchestrator.approve(run_id, actor="operator", approval_token=APPROVAL_TOKEN)

    state_path = tmp_path / "runs" / run_id / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["app_id"] = "upi_other_case"
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(OrchestrationConflict):
        orchestrator.execute(run_id)


def test_portfolio_store_still_rejects_external_non_tmp_roots() -> None:
    external = Path("/var/tmp") / "upi_app_factory_external_portfolio_contract"
    if external.is_relative_to(PROJECT_ROOT) or external.is_relative_to(Path("/tmp")):
        raise AssertionError("test external path must be outside project root and /tmp")
    with pytest.raises(PortfolioError):
        PortfolioStore(project_root=PROJECT_ROOT, state_root=external)


def test_source_identity_uses_git_manifest_and_deterministic_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPI_APP_FACTORY_SOURCE_COMMIT", raising=False)
    assert len(_source_commit(PROJECT_ROOT)) == 40

    source_only = tmp_path / "source_only"
    source_only.mkdir()
    commit = "a" * 40
    (source_only / "FACTORY_EXPORT_MANIFEST.json").write_text(
        json.dumps({"repository_commit": commit}) + "\n",
        encoding="utf-8",
    )
    assert _source_commit(source_only) == commit

    no_identity = tmp_path / "no_identity"
    no_identity.mkdir()
    assert _source_commit(no_identity) == "unavailable:deterministic_non_git_non_manifest_source_root"


def test_adapter_config_preserves_default_portfolio_registration_flag(tmp_path: Path) -> None:
    config = AdapterConfig(
        requirements=REQUIREMENTS_PATH,
        app_id="upi_failed_debit_no_credit",
        output_root=tmp_path / "workspace" / "generated",
        evidence_root=tmp_path / "workspace" / "evidence",
        approval_mode="proposal-only",
        approval_token=None,
        mock_safe=True,
        plan_only=True,
        replace_existing=False,
        factory_root=tmp_path,
        workspace_root=tmp_path / "workspace",
    )
    assert config.register_with_portfolio is True
