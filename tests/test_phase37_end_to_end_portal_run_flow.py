from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from factory.operator_portal.download_center import DownloadCenterService
from factory.operator_portal.end_to_end_run_flow import (
    SAFETY_BOUNDARIES,
    EndToEndPortalRunFlowService,
)
from factory.operator_portal.validation_runner import ValidationRunnerService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase37_end_to_end_portal_run_flow_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase37/end_to_end_portal_run_flow_prompt.md"


class FailingDownloadCenter:
    def trigger_governed_export(self) -> dict[str, Any]:
        raise RuntimeError("controlled export failure")


class FailingValidationRunner:
    def run(
        self,
        command_ids: tuple[str, ...] | None = None,
        *,
        dry_run: bool = False,
        collect_all: bool = False,
        write_report: bool = True,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "dry_run",
                "dry_run": True,
                "command_results": [{"command_id": "phase34_runner_self_check"}],
            }
        return {
            "status": "failed",
            "dry_run": False,
            "collect_all": collect_all,
            "report_path": "workspace/fake_phase34_report.json",
            "command_results": [
                {
                    "command_id": (command_ids or ("phase34_runner_self_check",))[0],
                    "status": "failed",
                    "return_code": 1,
                },
            ],
            "safety_boundaries": SAFETY_BOUNDARIES,
        }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase37_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase37_end_to_end_portal_run_flow.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_end_to_end_flow_exposes_required_stage_statuses(tmp_path: Path) -> None:
    report_path = tmp_path / "phase37_report.json"
    phase34_report_path = (
        PROJECT_ROOT
        / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/operator_portal_validation_run_report.json"
    )
    report = EndToEndPortalRunFlowService(
        validation_runner=ValidationRunnerService(report_path=phase34_report_path),
        report_path=report_path,
    ).run(validation_command_ids=("phase34_runner_self_check",))

    assert report["status"] == "passed"
    stages = report["stages"]
    assert set(stages) == {
        "intake_requirements_available",
        "generation_command",
        "export_bundle_ready",
        "validation_dry_run_ready",
        "validation_run",
        "evidence_dashboard_updated",
        "download_available",
    }
    assert stages["intake_requirements_available"]["status"] == "available"
    assert stages["generation_command"]["status"] in {"configured", "unavailable"}
    assert stages["generation_command"]["execution_status"] == "skipped"
    assert stages["export_bundle_ready"]["status"] == "passed"
    assert stages["validation_dry_run_ready"]["status"] == "passed"
    assert stages["validation_run"]["status"] == "passed"
    assert stages["evidence_dashboard_updated"]["status"] == "passed"
    assert stages["download_available"]["status"] == "passed"
    assert report_path.is_file()


def test_generation_configuration_does_not_claim_generation_success() -> None:
    report = EndToEndPortalRunFlowService().run(
        validation_command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    assert report["generation_status"]["success_claimed"] is False
    assert report["generation_status"]["generation_executed_by_phase37"] is False
    generation_stage = report["stages"]["generation_command"]
    assert generation_stage["success_claimed"] is False
    assert generation_stage["executed"] is False
    assert generation_stage["execution_status"] == "skipped"


def test_missing_intake_and_generation_configuration_are_reported_truthfully(
    tmp_path: Path,
) -> None:
    report = EndToEndPortalRunFlowService(
        project_root=tmp_path,
        download_center=cast(DownloadCenterService, FailingDownloadCenter()),
        validation_runner=cast(ValidationRunnerService, FailingValidationRunner()),
        report_path=tmp_path / "phase37_report.json",
    ).run()

    stages = report["stages"]
    assert stages["intake_requirements_available"]["status"] == "missing"
    assert stages["generation_command"]["status"] == "unavailable"
    assert stages["generation_command"]["execution_status"] == "skipped"
    assert stages["export_bundle_ready"]["status"] == "failed"
    assert stages["download_available"]["status"] == "missing"
    assert stages["validation_run"]["status"] == "failed"
    assert report["status"] == "failed"


def test_validation_failure_is_not_hidden(tmp_path: Path) -> None:
    report = EndToEndPortalRunFlowService(
        validation_runner=cast(ValidationRunnerService, FailingValidationRunner()),
        report_path=tmp_path / "phase37_report.json",
    ).run(write_report=False)

    assert report["stages"]["validation_run"]["status"] == "failed"
    assert report["status"] == "failed"


def test_governance_boundaries_remain_closed() -> None:
    policy = load_json(POLICY_PATH)
    report = EndToEndPortalRunFlowService().run(
        validation_command_ids=("phase34_runner_self_check",),
        write_report=False,
    )
    for field in [
        "official_certification_claimed",
        "official_certification_granted",
        "production_readiness_claimed",
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
    ]:
        assert policy[field] is False
        assert report["safety_boundaries"][field] is False
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert report["safety_boundaries"]["external_ecosystem_integrations"] == (
        "mocked_or_simulated_only"
    )
    assert report["safety_boundaries"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt


def test_unapproved_validation_command_is_rejected() -> None:
    with pytest.raises(ValueError):
        EndToEndPortalRunFlowService().run(
            validation_command_ids=("python -c arbitrary text",),
            write_report=False,
        )
