#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "phase42_generated_application_local_run_pack"
POLICY_PATH = Path("policies/phase42_generated_application_local_run_pack_policy.json")
PROMPT_PATH = Path("prompts/phase42/generated_application_local_run_pack_prompt.md")
VALIDATOR_PATH = Path("scripts/validate_phase42_generated_application_local_run_pack.py")
TEST_PATH = Path("tests/test_phase42_generated_application_local_run_pack.py")
GENERATED_APP_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase42"
)

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

REQUIRED_ENV_VALUES = {
    "UPI_DISPUTE_APP_ENV=local",
    "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE=mock",
    "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS=false",
    "UPI_DISPUTE_ALLOW_REAL_SECRETS=false",
    "UPI_DISPUTE_LOCAL_HOST=127.0.0.1",
}

LIVE_CALL_PATTERNS = [
    r"\brequests\.",
    r"\burllib\.request\b",
    r"\bhttpx\.(get|post|put|delete|patch|stream)\(",
    r"\bboto3\b",
    r"\bgoogle\.cloud\b",
    r"\bazure\.",
    r"\bstripe\b",
    r"\brazorpay\b",
]

REAL_SECRET_PATTERNS = [
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "client_secret =",
    "client_secret:",
    "api_key =",
    "api_key:",
    "secret_key =",
    "secret_key:",
    "password =",
]

RELEASE_ENABLEMENT_PATTERNS = [
    r'"deployment_allowed"\s*:\s*true',
    r'"merge_allowed"\s*:\s*true',
    r'"tag_allowed"\s*:\s*true',
    r'"push_allowed"\s*:\s*true',
    r"\bgit\s+push\b",
    r"\bgit\s+tag\b",
    r"\bgit\s+merge\b",
    r"\bnpm\s+publish\b",
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
    if gate.get("health_checks") != ["/health", "/runtime/health", "/runtime/metrics"]:
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
    reset_scope = reset_plan.get("reset_scope")
    if reset_scope != "known_local_runtime_noise_only":
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
    env_text = (PROJECT_ROOT / GENERATED_APP_ROOT / ".env.example").read_text(encoding="utf-8")
    for required in REQUIRED_ENV_VALUES:
        if required not in env_text:
            errors.append(f"Phase 42 .env.example missing {required}")

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

    startup_text = (PROJECT_ROOT / GENERATED_APP_ROOT / "scripts/start_local.sh").read_text(
        encoding="utf-8"
    )
    for marker in [
        "127.0.0.1",
        "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE",
        "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS",
        "UPI_DISPUTE_ALLOW_REAL_SECRETS",
        "uvicorn upi_dispute_app.main:app",
    ]:
        if marker not in startup_text:
            errors.append(f"Phase 42 startup script missing marker: {marker}")
    if ":-mock}" not in startup_text or ":-false}" not in startup_text:
        errors.append("Phase 42 startup script does not default to mock-only false live settings")

    smoke_text = (PROJECT_ROOT / GENERATED_APP_ROOT / "scripts/smoke_test.py").read_text(
        encoding="utf-8"
    )
    for marker in [
        "ASGITransport",
        "/health",
        "/disputes",
        "mock-ecosystem-check",
        "live_provider_calls_allowed",
    ]:
        if marker not in smoke_text:
            errors.append(f"Phase 42 smoke test missing marker: {marker}")

    clean_text = (
        PROJECT_ROOT / GENERATED_APP_ROOT / "scripts/clean_local_artifacts.sh"
    ).read_text(encoding="utf-8")
    if "var/local_runtime" not in clean_text or "export_bundles" in clean_text:
        errors.append("Phase 42 clean script is not scoped to local runtime noise")


def validate_no_boundary_violations(errors: list[str]) -> None:
    scan_paths = [
        POLICY_PATH,
        PROMPT_PATH,
        RUN_PACK_MANIFEST_PATH,
        READINESS_GATE_PATH,
        SMOKE_TEST_PLAN_PATH,
        RESET_PLAN_PATH,
        AUDIT_PATH,
        *RUN_PACK_FILES,
    ]
    for relative_path in scan_paths:
        path = PROJECT_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        for pattern in LIVE_CALL_PATTERNS:
            if re.search(pattern, text):
                errors.append(f"{relative_path} contains live-call pattern: {pattern}")
        for pattern in REAL_SECRET_PATTERNS:
            if pattern in text:
                errors.append(f"{relative_path} contains real-secret-like pattern: {pattern}")
        for pattern in RELEASE_ENABLEMENT_PATTERNS:
            if re.search(pattern, text):
                errors.append(f"{relative_path} contains release enablement pattern: {pattern}")
        if ".zip" in text:
            errors.append(f"{relative_path} references generated export bundle ZIP output")


def validate_local_smoke(errors: list[str]) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(GENERATED_APP_ROOT / "scripts/smoke_test.py"),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append("Phase 42 generated app smoke test failed:\n" + result.stdout + result.stderr)

    local_validator = subprocess.run(
        [
            sys.executable,
            str(GENERATED_APP_ROOT / "scripts/validate_local_run_pack.py"),
        ],
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
