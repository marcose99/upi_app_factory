from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from factory.operator_portal.evidence_dashboard import build_dashboard_summary
from factory.operator_portal.validation_runner import (
    DEFAULT_COMMAND_IDS,
    CommandNotAllowedError,
    ValidationRunnerService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase34_operator_portal_validation_runner_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase34/operator_portal_validation_runner_prompt.md"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase34_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase34_operator_portal_validation_runner.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_validation_runner_dry_run_returns_approved_commands() -> None:
    report = ValidationRunnerService().run(dry_run=True, write_report=False)
    assert report["dry_run"] is True
    assert [entry["command_id"] for entry in report["command_results"]] == list(
        DEFAULT_COMMAND_IDS,
    )
    assert all("return_code" not in entry for entry in report["command_results"])


def test_validation_runner_executes_only_allowlisted_commands(tmp_path: Path) -> None:
    report_path = tmp_path / "phase34_report.json"
    report = ValidationRunnerService(report_path=report_path).run(
        command_ids=("phase34_runner_self_check",),
    )
    assert report["status"] == "passed"
    assert report["command_results"][0]["command_id"] == "phase34_runner_self_check"
    assert report_path.is_file()


def test_unapproved_arbitrary_commands_are_rejected() -> None:
    service = ValidationRunnerService()
    with pytest.raises(CommandNotAllowedError):
        service.run(command_ids=("python -c 'print(123)'",), write_report=False)


def test_structured_validation_report_contains_status_and_return_code(tmp_path: Path) -> None:
    report_path = tmp_path / "phase34_report.json"
    report = ValidationRunnerService(report_path=report_path).run(
        command_ids=("phase34_runner_self_check",),
    )
    persisted = load_json(report_path)
    assert persisted["phase"] == "phase34_operator_portal_governed_validation_runner"
    assert persisted["command_results"] == report["command_results"]
    command = persisted["command_results"][0]
    assert command["status"] == "passed"
    assert command["return_code"] == 0


def test_report_preserves_certification_ready_not_certified_boundary() -> None:
    report = ValidationRunnerService().run(
        command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    assert report["safety_boundaries"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )


def test_official_certification_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    report = ValidationRunnerService().run(
        command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert report["safety_boundaries"]["official_certification_claimed"] is False
    assert report["safety_boundaries"]["official_certification_granted"] is False


def test_production_readiness_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    report = ValidationRunnerService().run(
        command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    assert policy["production_readiness_claimed"] is False
    assert report["safety_boundaries"]["production_readiness_claimed"] is False


def test_live_provider_calls_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    report = ValidationRunnerService().run(
        command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    assert policy["live_provider_calls_allowed"] is False
    assert report["safety_boundaries"]["live_provider_calls_allowed"] is False


def test_real_secrets_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    report = ValidationRunnerService().run(
        command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    assert policy["real_secrets_allowed"] is False
    assert report["safety_boundaries"]["real_secrets_allowed"] is False


def test_deployment_merge_tag_push_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    report = ValidationRunnerService().run(
        command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    for field in ["deployment_allowed", "merge_allowed", "tag_allowed", "push_allowed"]:
        assert policy[field] is False
        assert report["safety_boundaries"][field] is False


def test_phase33_dashboard_reports_phase34_run_report_availability_truthfully(
    tmp_path: Path,
) -> None:
    missing = build_dashboard_summary(project_root=tmp_path)
    assert missing["phase34_validation_runner_report_status"]["status"] == "missing"

    report_path = (
        PROJECT_ROOT
        / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_run_report.json"
    )
    ValidationRunnerService(report_path=report_path).run(
        command_ids=("phase34_runner_self_check",),
    )
    available = build_dashboard_summary()
    assert available["phase34_validation_runner_report_status"]["run_report_status"] == (
        "available"
    )


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
