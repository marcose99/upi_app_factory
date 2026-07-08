from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.evidence_dashboard import build_dashboard_summary


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase33_operator_portal_evidence_dashboard_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase33/operator_portal_evidence_dashboard_prompt.md"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def dashboard_summary() -> dict[str, Any]:
    return build_dashboard_summary()


def test_phase33_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase33_operator_portal_evidence_dashboard.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_summary_is_returned() -> None:
    summary = dashboard_summary()
    assert summary["app_id"] == "upi_dispute_resolution"
    assert summary["phase"] == "phase33_operator_portal_run_validation_evidence_dashboard"
    assert summary["latest_relevant_tags"]["status"] in {"available", "unknown"}


def test_phase28_through_phase32_evidence_is_visible() -> None:
    summary = dashboard_summary()
    artifacts = summary["lifecycle_artifact_availability"]
    for phase in ["phase28", "phase29", "phase30", "phase31", "phase32"]:
        assert phase in artifacts
        assert artifacts[phase]["status"] in {"available", "partial", "missing"}
        assert artifacts[phase]["files"]


def test_phase31_bundle_metadata_and_phase32_status_are_visible() -> None:
    summary = dashboard_summary()
    bundle = summary["phase31_export_bundle_metadata"]
    phase32 = summary["phase32_download_center_service_status"]
    assert bundle["status"] in {"available", "partial", "missing"}
    assert "bundle_ready" in bundle
    assert phase32["service_path"] == "factory/operator_portal/download_center.py"
    assert phase32["status"] in {"available", "missing"}


def test_validator_and_test_commands_are_visible() -> None:
    summary = dashboard_summary()
    assert "python scripts/validate_phase33_operator_portal_evidence_dashboard.py" in (
        summary["validator_commands"]
    )
    assert "python -m pytest tests/test_phase33_operator_portal_evidence_dashboard.py" in (
        summary["test_commands"]
    )


def test_certification_ready_not_certified_boundary_is_preserved() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert summary["safety_boundaries"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )
    assert summary["phase_coverage"]["posture"] == "certification_ready_not_certified"


def test_official_certification_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert summary["safety_boundaries"]["official_certification_claimed"] is False
    assert summary["safety_boundaries"]["official_certification_granted"] is False


def test_production_readiness_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["production_readiness_claimed"] is False
    assert summary["safety_boundaries"]["production_readiness_claimed"] is False


def test_live_provider_calls_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["live_provider_calls_allowed"] is False
    assert summary["safety_boundaries"]["live_provider_calls_allowed"] is False


def test_real_secrets_are_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["real_secrets_allowed"] is False
    assert summary["safety_boundaries"]["real_secrets_allowed"] is False


def test_deployment_is_not_enabled() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["deployment_allowed"] is False
    assert summary["safety_boundaries"]["deployment_allowed"] is False


def test_mocked_simulated_ecosystem_boundary_is_preserved() -> None:
    policy = load_json(POLICY_PATH)
    summary = dashboard_summary()
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert summary["safety_boundaries"]["external_ecosystem_integrations"] == (
        "mocked_or_simulated_only"
    )
    assert summary["safety_boundaries"]["mocked_simulated_ecosystem_boundary"] is True


def test_dashboard_reports_missing_instead_of_fake_success_when_evidence_absent(
    tmp_path: Path,
) -> None:
    summary = build_dashboard_summary(project_root=tmp_path)
    artifacts = summary["lifecycle_artifact_availability"]
    for phase in ["phase28", "phase29", "phase30", "phase31", "phase32"]:
        assert artifacts[phase]["status"] == "missing"
        assert all(file_entry["status"] == "missing" for file_entry in artifacts[phase]["files"])
    assert summary["phase31_export_bundle_metadata"]["status"] == "missing"
    assert summary["dashboard_success_claim"]["status"] == "not_claimed"


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
