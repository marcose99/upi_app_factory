from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase31_deep_generated_application_export_download_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase31/deep_generated_application_export_download_prompt.md"
GENERATED_WORKSPACE = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def run_export() -> tuple[Path, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, "scripts/export_phase31_deep_generated_application_bundle.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return PROJECT_ROOT / payload["zip_path"], cast(dict[str, Any], payload)


def zip_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    value = json.loads(archive.read(name).decode("utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def workspace_files() -> set[str]:
    return {
        str(path.relative_to(GENERATED_WORKSPACE))
        for path in GENERATED_WORKSPACE.rglob("*")
        if path.is_file()
    }


def test_phase31_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase31_deep_generated_application_export_download_center.py",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_export_script_creates_zip_bundle() -> None:
    zip_path, payload = run_export()
    assert zip_path.is_file()
    assert zip_path.suffix == ".zip"
    assert payload["existing_generated_workspace_destructively_replaced"] is False


def test_bundle_contains_generated_application_deep_structure() -> None:
    zip_path, _payload = run_export()
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    for relative_dir in [
        "generated_application_export/generated_application/app/domain/",
        "generated_application_export/generated_application/app/application/",
        "generated_application_export/generated_application/app/infrastructure/",
        "generated_application_export/generated_application/app/interfaces/",
        "generated_application_export/generated_application/app/observability/",
        "generated_application_export/generated_application/app/security/",
        "generated_application_export/generated_application/app/tests/",
    ]:
        assert any(name.startswith(relative_dir) for name in names)
    assert (
        "generated_application_export/generated_application/app/domain/entities.py" in names
    )
    assert (
        "generated_application_export/generated_application/app/interfaces/api/main.py" in names
    )


def test_bundle_contains_generation_manifest_and_evidence() -> None:
    zip_path, _payload = run_export()
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        export_manifest = zip_json(archive, "export_manifest.json")
        generation_manifest = zip_json(archive, "generation_manifest.json")
    assert "generation_manifest.json" in names
    assert "export_manifest.json" in names
    assert "evidence/phase28_architecture_depth_inputs_summary.json" in names
    assert "evidence/phase29_deep_structure_policy_summary.json" in names
    assert (
        "evidence/phase30_regeneration_certification_readiness_evidence_summary.json"
        in names
    )
    assert "evidence/source_evidence_file_index.json" in names
    assert export_manifest["evidence_files"]
    assert generation_manifest["phase29_deep_structure_policy_recorded"] is True


def test_bundle_preserves_certification_ready_not_certified_boundary() -> None:
    zip_path, _payload = run_export()
    with zipfile.ZipFile(zip_path) as archive:
        export_manifest = zip_json(archive, "export_manifest.json")
        boundary = zip_json(archive, "evidence/certification_ready_not_certified_boundary.json")
    assert export_manifest["certification_boundary"] == "certification_ready_not_certified"
    assert boundary["certification_boundary"] == "certification_ready_not_certified"


def test_bundle_does_not_claim_official_certification() -> None:
    zip_path, _payload = run_export()
    with zipfile.ZipFile(zip_path) as archive:
        export_manifest = zip_json(archive, "export_manifest.json")
        text = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore").lower()
            for name in archive.namelist()
            if not name.endswith("/")
        )
    assert export_manifest["official_certification_claimed"] is False
    assert export_manifest["official_certification_granted"] is False
    assert "officially certified" not in text
    assert "official certification granted" not in text
    assert "npci certified" not in text


def test_bundle_does_not_enable_live_provider_calls() -> None:
    zip_path, _payload = run_export()
    with zipfile.ZipFile(zip_path) as archive:
        export_manifest = zip_json(archive, "export_manifest.json")
        no_live = zip_json(
            archive,
            "evidence/no_live_provider_no_real_secret_no_deployment_no_official_certification_evidence.json",
        )
        text = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if not name.endswith("/")
        )
    assert export_manifest["live_provider_calls_allowed"] is False
    assert no_live["live_provider_calls_allowed"] is False
    assert "requests." not in text
    assert "httpx." not in text
    assert "boto3" not in text


def test_bundle_does_not_include_real_secrets() -> None:
    zip_path, _payload = run_export()
    with zipfile.ZipFile(zip_path) as archive:
        text = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if not name.endswith("/")
        )
    assert "-----BEGIN PRIVATE KEY-----" not in text
    assert "api_key=" not in text.lower()
    assert "password=" not in text.lower()


def test_existing_generated_workspace_is_not_destructively_replaced() -> None:
    before = workspace_files()
    _zip_path, payload = run_export()
    after = workspace_files()
    assert before == after
    assert payload["existing_generated_workspace_destructively_replaced"] is False


def test_shared_prompt_contracts_remain_inherited() -> None:
    policy = load_json(POLICY_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
