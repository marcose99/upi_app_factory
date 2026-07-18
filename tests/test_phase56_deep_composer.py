from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from factory.application_engineering.deep_composer import (
    DeepApplicationComposer,
    DeepComposerError,
    GOLDEN_APP_ID,
    REQUIRED_ENDPOINTS,
)
from factory.application_engineering.requirements_compiler import compile_requirements


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase53" / "failed_debit_requirements.md"


def requirements_ir() -> dict[str, object]:
    return compile_requirements([FIXTURE], ROOT)


def workspace_tmp(name: str) -> Path:
    path = ROOT / "workspace" / "deep_engineering_campaign" / "phase56_test_runs" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def test_composer_generates_golden_app_with_deep_profile() -> None:
    output = workspace_tmp("golden")
    result = DeepApplicationComposer(ROOT).compose(
        requirements_ir=requirements_ir(),
        output_root=output,
        app_id=GOLDEN_APP_ID,
    )

    assert result["composer_profile"] == "local-deep-v1"
    assert result["app_id"] == "upi_failed_debit_dispute"
    assert result["persistence"] == "sqlite-stdlib"
    assert result["llm_runtime_calls"] == 0
    assert result["real_payment_calls"] == "disabled"
    assert set(result["endpoints"]) == set(REQUIRED_ENDPOINTS)

    expected_files = {
        "app/upi_failed_debit_dispute/interfaces/api/main.py",
        "app/upi_failed_debit_dispute/infrastructure/persistence/migrations/0001_initial.sql",
        "configuration/example.env",
        "scripts/run_local.sh",
        "openapi/openapi.json",
        "docs/domain_state_machine.md",
        "docs/adrs/ADR-0001-local-sqlite-modular-monolith.md",
        "docs/threat_model.md",
        "docs/operations_runbook.md",
        "docs/test_plan.md",
        "evidence/generation_manifest.json",
        "evidence/depth_score.json",
    }
    actual_files = {item["path"] for item in result["file_manifest"]}
    assert expected_files.issubset(actual_files)


def test_composer_is_deterministic_for_same_ir() -> None:
    output = workspace_tmp("deterministic")
    composer = DeepApplicationComposer(ROOT)
    first = composer.compose(requirements_ir=requirements_ir(), output_root=output / "one")
    second = composer.compose(requirements_ir=requirements_ir(), output_root=output / "two")

    first_manifest = {
        item["path"]: item["sha256"]
        for item in first["file_manifest"]
        if item["path"] != "evidence/generation_manifest.json"
    }
    second_manifest = {
        item["path"]: item["sha256"]
        for item in second["file_manifest"]
        if item["path"] != "evidence/generation_manifest.json"
    }
    assert first_manifest == second_manifest


def test_composer_rejects_default_factory_namespace() -> None:
    with pytest.raises(DeepComposerError):
        DeepApplicationComposer(ROOT).compose(
            requirements_ir=requirements_ir(),
            output_root=workspace_tmp("namespace"),
            app_id="upi_app_factory",
        )


def test_generated_api_contract_contains_required_routes() -> None:
    output = workspace_tmp("api_contract")
    DeepApplicationComposer(ROOT).compose(requirements_ir=requirements_ir(), output_root=output)
    api_text = (
        output
        / GOLDEN_APP_ID
        / "app"
        / GOLDEN_APP_ID
        / "interfaces"
        / "api"
        / "main.py"
    ).read_text(encoding="utf-8")
    for route in [
        '"/health"',
        '"/ready"',
        '"/metrics"',
        '"/v1/disputes"',
        '"/v1/disputes/{dispute_id}/audit"',
    ]:
        assert route in api_text

    openapi = json.loads((output / GOLDEN_APP_ID / "openapi" / "openapi.json").read_text(encoding="utf-8"))
    assert set(openapi["x-required-endpoints"]) == set(REQUIRED_ENDPOINTS)
