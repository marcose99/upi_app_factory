from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from factory.operator_portal.download_center import DownloadCenterService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase32_operator_portal_download_center_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase32/operator_portal_download_center_prompt.md"
GENERATED_WORKSPACE = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def workspace_files() -> set[str]:
    if not GENERATED_WORKSPACE.exists():
        return set()
    return {
        str(path.relative_to(GENERATED_WORKSPACE))
        for path in GENERATED_WORKSPACE.rglob("*")
        if path.is_file()
    }


def run_download_center() -> dict[str, Any]:
    return DownloadCenterService().trigger_governed_export()


def test_phase32_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase32_operator_portal_download_center.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_download_center_invokes_phase31_export_capability() -> None:
    invoked = {"value": False}

    def export_runner() -> dict[str, Any]:
        invoked["value"] = True
        return run_download_center_payload()

    result = DownloadCenterService(export_runner=export_runner).trigger_governed_export()
    assert invoked["value"] is True
    assert result["phase31_export_invoked"] is True
    assert result["status"] == "export_ready"


def run_download_center_payload() -> dict[str, Any]:
    from scripts.export_phase31_deep_generated_application_bundle import export_bundle

    return export_bundle(clean=True)


def test_bundle_metadata_is_returned() -> None:
    result = run_download_center()
    metadata = result["bundle_metadata"]
    assert metadata["bundle_id"] == "phase31_deep_generated_application_bundle"
    assert metadata["app_id"] == "upi_dispute_resolution"
    assert metadata["phase32_service_phase"] == "phase32_operator_portal_download_center_integration"
    assert metadata["certification_boundary"] == "certification_ready_not_certified"


def test_export_manifest_is_readable_through_download_service() -> None:
    service = DownloadCenterService()
    result = service.trigger_governed_export()
    manifest = service.get_manifest(result)
    assert manifest["phase"] == "phase31_deep_generated_application_export_download_center"
    assert manifest["generated_application_root"] == (
        "generated_application_export/generated_application"
    )
    assert manifest["destructive_workspace_replacement"] is False


def test_evidence_summaries_are_readable() -> None:
    service = DownloadCenterService()
    result = service.trigger_governed_export()
    evidence = service.get_evidence_summaries(result)
    assert "evidence/phase28_architecture_depth_inputs_summary.json" in evidence
    assert "evidence/phase29_deep_structure_policy_summary.json" in evidence
    assert (
        "evidence/phase30_regeneration_certification_readiness_evidence_summary.json"
        in evidence
    )
    assert "evidence/certification_ready_not_certified_boundary.json" in evidence


def test_download_path_points_to_existing_zip() -> None:
    result = run_download_center()
    download_path = Path(result["download_ready_path"])
    local_bundle_path = Path(result["local_bundle_path"])
    assert download_path.is_file()
    assert local_bundle_path.is_file()
    assert download_path.suffix == ".zip"
    assert result["bundle_path"].endswith(".zip")


def test_no_live_provider_calls_are_introduced() -> None:
    result = run_download_center()
    metadata = result["bundle_metadata"]
    boundaries = result["safety_boundaries"]
    assert metadata["live_provider_calls_allowed"] is False
    assert boundaries["live_provider_calls_allowed"] is False
    service_source = (
        PROJECT_ROOT / "factory/operator_portal/download_center.py"
    ).read_text(encoding="utf-8")
    assert "requests." not in service_source
    assert "urllib.request" not in service_source
    assert "boto3" not in service_source


def test_no_real_secrets_are_introduced() -> None:
    result = run_download_center()
    metadata = result["bundle_metadata"]
    boundaries = result["safety_boundaries"]
    assert metadata["real_secrets_allowed"] is False
    assert boundaries["real_secrets_allowed"] is False
    service_source = (
        PROJECT_ROOT / "factory/operator_portal/download_center.py"
    ).read_text(encoding="utf-8")
    assert "-----BEGIN PRIVATE KEY-----" not in service_source
    assert "api_key=" not in service_source.lower()
    assert "password=" not in service_source.lower()


def test_existing_generated_workspace_is_not_destructively_replaced() -> None:
    before = workspace_files()
    result = run_download_center()
    after = workspace_files()
    assert before == after
    assert result["export_manifest"]["destructive_workspace_replacement"] is False
    assert result["safety_boundaries"]["destructive_workspace_replacement_allowed"] is False


def test_certification_ready_not_certified_boundary_is_preserved() -> None:
    result = run_download_center()
    assert result["bundle_metadata"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )
    assert result["export_manifest"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )
    assert result["safety_boundaries"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )


def test_official_certification_is_not_claimed() -> None:
    policy = load_json(POLICY_PATH)
    result = run_download_center()
    assert policy["official_certification_claimed"] is False
    assert policy["official_certification_granted"] is False
    assert result["bundle_metadata"]["official_certification_claimed"] is False
    assert result["export_manifest"]["official_certification_claimed"] is False
    assert result["export_manifest"]["official_certification_granted"] is False


def test_shared_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt


def test_download_center_rejects_fake_generation_success() -> None:
    def fake_export_runner() -> dict[str, Any]:
        return {
            "bundle_id": "fake",
            "zip_path": "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/fake.zip",
            "manifest_path": "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/fake/export_manifest.json",
            "generation_manifest_path": "workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/fake/generation_manifest.json",
            "existing_generated_workspace_destructively_replaced": False,
        }

    with pytest.raises(RuntimeError):
        DownloadCenterService(export_runner=fake_export_runner).trigger_governed_export()
