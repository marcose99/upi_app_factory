from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_APP_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
POLICY_PATH = PROJECT_ROOT / "policies/phase42_generated_application_local_run_pack_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase42/generated_application_local_run_pack_prompt.md"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase42"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase42_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase42_generated_application_local_run_pack.py",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_policy_prompt_and_artifacts_preserve_governance_boundaries() -> None:
    artifacts = [
        load_json(POLICY_PATH),
        load_json(ARTIFACT_DIR / "generated_application_local_run_pack_manifest.json"),
        load_json(ARTIFACT_DIR / "generated_application_local_run_readiness_gate.json"),
        load_json(ARTIFACT_DIR / "generated_application_local_smoke_test_plan.json"),
        load_json(ARTIFACT_DIR / "generated_application_local_artifact_reset_plan.json"),
        load_json(ARTIFACT_DIR / "generated_application_local_run_pack_audit.json"),
    ]
    for artifact in artifacts:
        assert artifact["certification_boundary"] == "certification_ready_not_certified"
        assert artifact["official_certification_claimed"] is False
        assert artifact["official_certification_granted"] is False
        assert artifact["production_readiness_claimed"] is False
        assert artifact["live_provider_calls_allowed"] is False
        assert artifact["real_secrets_allowed"] is False
        assert artifact["deployment_allowed"] is False
        assert artifact["merge_allowed"] is False
        assert artifact["tag_allowed"] is False
        assert artifact["push_allowed"] is False
        assert artifact["external_ecosystem_integrations"] == "mocked_or_simulated_only"
        assert artifact["local_readiness_scope"] == "local_generated_application_run_pack_review_only"

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt


def test_run_pack_files_and_reset_scope_are_present() -> None:
    policy = load_json(POLICY_PATH)
    for relative_path in policy["required_run_pack_files"]:
        assert (PROJECT_ROOT / relative_path).is_file()

    reset_plan = load_json(ARTIFACT_DIR / "generated_application_local_artifact_reset_plan.json")
    assert reset_plan["reset_scope"] == "known_local_runtime_noise_only"
    assert "workspace/factory_generated/upi_dispute_resolution/export_bundles" in reset_plan[
        "must_not_remove"
    ]

    docs = (GENERATED_APP_ROOT / "docs/local_run_pack/README.md").read_text(encoding="utf-8")
    assert "scripts/start_local.sh" in docs
    assert "scripts/health_check.py" in docs
    assert "scripts/smoke_test.py" in docs
    assert "scripts/clean_local_artifacts.sh" in docs


def test_env_example_and_startup_script_are_mock_only() -> None:
    env_text = (GENERATED_APP_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE=mock" in env_text
    assert "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS=false" in env_text
    assert "UPI_DISPUTE_ALLOW_REAL_SECRETS=false" in env_text
    assert "UPI_DISPUTE_LOCAL_HOST=127.0.0.1" in env_text

    startup_text = (GENERATED_APP_ROOT / "scripts/start_local.sh").read_text(encoding="utf-8")
    assert "127.0.0.1" in startup_text
    assert ":-mock}" in startup_text
    assert ":-false}" in startup_text
    assert "uvicorn generated_application.app.interfaces.api.main:app" in startup_text
    assert "upi_dispute_app.main:app" not in startup_text


def test_generated_app_smoke_script_exercises_local_behavior() -> None:
    smoke_text = (GENERATED_APP_ROOT / "scripts/smoke_test.py").read_text(encoding="utf-8")
    assert "local_principal" in smoke_text
    assert "app.openapi" in smoke_text
    assert "METRICS.openmetrics" in smoke_text

    result = subprocess.run(
        [sys.executable, str(GENERATED_APP_ROOT / "scripts/smoke_test.py")],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "local smoke test passed" in result.stdout.lower()


def test_no_phase42_release_or_live_provider_enablement() -> None:
    scanned_paths = [
        POLICY_PATH,
        PROMPT_PATH,
        GENERATED_APP_ROOT / ".env.example",
        GENERATED_APP_ROOT / "docs/local_run_pack/README.md",
        GENERATED_APP_ROOT / "scripts/start_local.sh",
        GENERATED_APP_ROOT / "scripts/health_check.py",
        GENERATED_APP_ROOT / "scripts/smoke_test.py",
        GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py",
        GENERATED_APP_ROOT / "scripts/clean_local_artifacts.sh",
    ]
    scanned_text = "\n".join(path.read_text(encoding="utf-8") for path in scanned_paths)
    assert "BEGIN PRIVATE KEY" not in scanned_text
    assert "boto3" not in scanned_text
    assert "google.cloud" not in scanned_text
    assert '"deployment_allowed": true' not in scanned_text
    assert '"push_allowed": true' not in scanned_text
    assert "git push" not in scanned_text
    assert "git tag" not in scanned_text
    assert "git merge" not in scanned_text
    assert ".zip" not in scanned_text
