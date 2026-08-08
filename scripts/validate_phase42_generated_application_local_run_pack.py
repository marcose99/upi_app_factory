#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.current_operational_contract import (  # noqa: E402
    find_executable_boundary_violations,
    find_secret_like_text,
    load_application_profile,
    recipient_test_command,
    required_local_run_environment,
)

APP_ID = "upi_dispute_resolution"
PHASE = "phase42_generated_application_local_run_pack"
POLICY_PATH = Path("policies/phase42_generated_application_local_run_pack_policy.json")
PROMPT_PATH = Path("prompts/phase42/generated_application_local_run_pack_prompt.md")
VALIDATOR_PATH = Path("scripts/validate_phase42_generated_application_local_run_pack.py")
TEST_PATH = Path("tests/test_phase42_generated_application_local_run_pack.py")
GENERATED_APP_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase42"

RUN_PACK_MANIFEST_PATH = ARTIFACT_DIR / "generated_application_local_run_pack_manifest.json"
READINESS_GATE_PATH = ARTIFACT_DIR / "generated_application_local_run_readiness_gate.json"
SMOKE_TEST_PLAN_PATH = ARTIFACT_DIR / "generated_application_local_smoke_test_plan.json"
RESET_PLAN_PATH = ARTIFACT_DIR / "generated_application_local_artifact_reset_plan.json"
AUDIT_PATH = ARTIFACT_DIR / "generated_application_local_run_pack_audit.json"

RUN_PACK_FILES = [
    GENERATED_APP_ROOT / ".env.example",
    GENERATED_APP_ROOT / "README.md",
    GENERATED_APP_ROOT / "docs/local_run_pack/README.md",
    GENERATED_APP_ROOT / "scripts/start_local.sh",
    GENERATED_APP_ROOT / "scripts/health_check.py",
    GENERATED_APP_ROOT / "scripts/smoke_test.py",
    GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py",
    GENERATED_APP_ROOT / "scripts/clean_local_artifacts.sh",
]

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    VALIDATOR_PATH,
    TEST_PATH,
    RUN_PACK_MANIFEST_PATH,
    READINESS_GATE_PATH,
    SMOKE_TEST_PLAN_PATH,
    RESET_PLAN_PATH,
    AUDIT_PATH,
    *RUN_PACK_FILES,
]

REQUIRED_BOUNDARY_FIELDS = [
    "official_certification_claimed",
    "official_certification_granted",
    "production_readiness_claimed",
    "live_provider_calls_allowed",
    "real_secrets_allowed",
    "deployment_allowed",
    "merge_allowed",
    "tag_allowed",
    "push_allowed",
]

EXECUTABLE_SCAN_PATHS = [
    GENERATED_APP_ROOT / ".env.example",
    GENERATED_APP_ROOT / "scripts/start_local.sh",
    GENERATED_APP_ROOT / "scripts/health_check.py",
    GENERATED_APP_ROOT / "scripts/smoke_test.py",
    GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py",
    GENERATED_APP_ROOT / "scripts/clean_local_artifacts.sh",
]

DOCUMENTATION_SCAN_PATHS = [
    PROMPT_PATH,
    GENERATED_APP_ROOT / "README.md",
    GENERATED_APP_ROOT / "docs/local_run_pack/README.md",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_boundary_artifact(
    artifact: dict[str, Any],
    errors: list[str],
    context: str,
) -> None:
    if artifact.get("certification_boundary") != "certification_ready_not_certified":
        errors.append(f"{context} changed certification boundary")
    for field in REQUIRED_BOUNDARY_FIELDS:
        if artifact.get(field) is not False:
            errors.append(f"{context} has invalid boundary field: {field}")
    if artifact.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append(f"{context} does not keep ecosystem integrations mocked")
    if artifact.get("local_readiness_scope") != "local_generated_application_run_pack_review_only":
        errors.append(f"{context} does not scope readiness to local run-pack review only")


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not (PROJECT_ROOT / path).exists():
            errors.append(f"Missing required Phase 42 file: {path}")


def validate_policy_prompt_and_lifecycle_artifacts(errors: list[str]) -> None:
    policy = load_json(PROJECT_ROOT / POLICY_PATH)
    manifest = load_json(PROJECT_ROOT / RUN_PACK_MANIFEST_PATH)
    gate = load_json(PROJECT_ROOT / READINESS_GATE_PATH)
    smoke_plan = load_json(PROJECT_ROOT / SMOKE_TEST_PLAN_PATH)
    reset_plan = load_json(PROJECT_ROOT / RESET_PLAN_PATH)
    audit = load_json(PROJECT_ROOT / AUDIT_PATH)
    prompt = (PROJECT_ROOT / PROMPT_PATH).read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE42-GENERATED-APPLICATION-LOCAL-RUN-PACK-GATE":
        errors.append("Phase 42 policy missing mandatory gate")
    if policy.get("validation_entrypoint") != str(VALIDATOR_PATH):
        errors.append("Phase 42 policy does not identify validator")
    if policy.get("test_entrypoint") != str(TEST_PATH):
        errors.append("Phase 42 policy does not identify tests")
    if gate.get("gate_status") != "passed":
        errors.append("Phase 42 local run readiness gate is not passed")
    if gate.get("health_checks") != ["/health", "/startup", "/live", "/ready", "/metrics"]:
        errors.append("Phase 42 gate does not list required health checks")

    for artifact, name in [
        (policy, "policy"),
        (manifest, "manifest"),
        (gate, "gate"),
        (smoke_plan, "smoke test plan"),
        (reset_plan, "reset plan"),
        (audit, "audit"),
    ]:
        validate_boundary_artifact(artifact, errors, f"Phase 42 {name}")
        if artifact.get("phase") != PHASE:
            errors.append(f"Phase 42 {name} has wrong phase")

    required_run_pack_files = set(policy.get("required_run_pack_files", []))
    actual_run_pack_files = {str(path) for path in RUN_PACK_FILES if path.name != "README.md"}
    if not actual_run_pack_files.issubset(required_run_pack_files):
        errors.append("Phase 42 policy does not list all required run-pack files")

    smoke_steps = smoke_plan.get("smoke_steps")
    if not isinstance(smoke_steps, list) or len(smoke_steps) < 5:
        errors.append("Phase 42 smoke test plan is incomplete")
    if reset_plan.get("reset_scope") != "known_local_runtime_noise_only":
        errors.append("Phase 42 reset plan is not limited to known runtime noise")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        include = "{{ include: " + contract_path + " }}"
        if include not in prompt:
            errors.append(f"Phase 42 prompt does not inherit contract: {contract_path}")


def validate_run_pack_content(errors: list[str]) -> None:
    profile = load_application_profile(APP_ID)

    env_text = (PROJECT_ROOT / GENERATED_APP_ROOT / ".env.example").read_text(encoding="utf-8")
    for required in required_local_run_environment(APP_ID, profile):
        if required not in env_text:
            errors.append(f"Phase 42 .env.example missing profile value: {required}")

    doc_text = (
        PROJECT_ROOT / GENERATED_APP_ROOT / "docs/local_run_pack/README.md"
    ).read_text(encoding="utf-8")
    for marker in [
        "scripts/start_local.sh",
        "scripts/health_check.py",
        "scripts/smoke_test.py",
        "scripts/clean_local_artifacts.sh",
        "certification_ready_not_certified",
        "mocked or simulated",
    ]:
        if marker not in doc_text:
            errors.append(f"Phase 42 local run documentation missing marker: {marker}")

    deployment_guide = (
        PROJECT_ROOT / "docs/deployment/GENERATED_APPLICATION_LOCAL_DEPLOYMENT_GUIDE.md"
    ).read_text(encoding="utf-8")
    current_command = recipient_test_command(APP_ID, profile)
    if current_command not in deployment_guide:
        errors.append(
            "Deployment guide does not document application-profile recipient test "
            f"command: {current_command}"
        )
    if "python -m pytest -q generated_application/app/tests" in deployment_guide:
        errors.append("Deployment guide uses stale nested generated_application test path")

    startup_text = (
        PROJECT_ROOT / GENERATED_APP_ROOT / "scripts/start_local.sh"
    ).read_text(encoding="utf-8")
    for marker in [
        "127.0.0.1",
        "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE",
        "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS",
        "UPI_DISPUTE_ALLOW_REAL_SECRETS",
        "uvicorn generated_application.app.interfaces.api.main:app",
    ]:
        if marker not in startup_text:
            errors.append(f"Phase 42 startup script missing marker: {marker}")
    if "upi_dispute_app.main:app" in startup_text:
        errors.append("Phase 42 startup script still launches legacy app")
    if ":-mock}" not in startup_text or ":-false}" not in startup_text:
        errors.append("Phase 42 startup script does not default to mock-only false live settings")

    smoke_text = (
        PROJECT_ROOT / GENERATED_APP_ROOT / "scripts/smoke_test.py"
    ).read_text(encoding="utf-8")
    for marker in ["local_principal", "app.openapi", "/disputes", "METRICS.openmetrics", "401"]:
        if marker not in smoke_text:
            errors.append(f"Phase 42 smoke test missing marker: {marker}")

    clean_text = (
        PROJECT_ROOT / GENERATED_APP_ROOT / "scripts/clean_local_artifacts.sh"
    ).read_text(encoding="utf-8")
    if "var/local_runtime" not in clean_text or "export_bundles" in clean_text:
        errors.append("Phase 42 clean script is not scoped to local runtime noise")


def validate_no_boundary_violations(errors: list[str]) -> None:
    for relative_path in EXECUTABLE_SCAN_PATHS:
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for pattern in find_secret_like_text(text):
            errors.append(f"{relative_path} contains secret-like pattern: {pattern}")
        for pattern in find_executable_boundary_violations(text):
            errors.append(f"{relative_path} contains executable boundary pattern: {pattern}")

    for relative_path in DOCUMENTATION_SCAN_PATHS:
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for pattern in find_secret_like_text(text):
            errors.append(f"{relative_path} contains secret-like pattern: {pattern}")


def validate_local_smoke(errors: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATED_APP_ROOT / "scripts/smoke_test.py")],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append("Phase 42 generated app smoke test failed:\n" + result.stdout + result.stderr)

    local_validator = subprocess.run(
        [sys.executable, str(GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py")],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if local_validator.returncode != 0:
        errors.append(
            "Phase 42 generated app local run-pack validator failed:\n"
            + local_validator.stdout
            + local_validator.stderr
        )


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    if not errors:
        validate_policy_prompt_and_lifecycle_artifacts(errors)
        validate_run_pack_content(errors)
        validate_no_boundary_violations(errors)
        validate_local_smoke(errors)

    if errors:
        print("Phase 42 generated application local run pack validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase 42 generated application local run pack validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
