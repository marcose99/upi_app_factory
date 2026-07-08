#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, cast

from factory.generators.mock_dispute_app_generator import generate


APP_ID = "upi_dispute_resolution"
POLICY_PATH = Path("policies/phase30_deep_generated_application_regeneration_policy.json")
PROMPT_PATH = Path("prompts/phase30/deep_generated_application_regeneration_prompt.md")
PHASE29_POLICY_PATH = Path("policies/phase29_generated_application_deep_structure_policy.json")
TEMPLATE_MANIFEST_PATH = Path("factory/templates/mock_dispute_app/template_manifest.v1.json")
GENERATOR_PATH = Path("factory/generators/mock_dispute_app_generator.py")
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase30"

PHASE28_INPUTS = {
    "factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json",
    "policies/phase28_generated_application_architecture_depth_policy.json",
    "prompts/phase28/generated_application_architecture_depth_prompt.md",
}

TEST_OBLIGATIONS = {
    "unit",
    "integration",
    "contract",
    "negative",
    "resilience",
    "security",
    "performance_smoke",
    "replay",
    "audit",
}

TEST_OBLIGATION_DIRS = {
    "unit": "generated_application/app/tests/unit/",
    "integration": "generated_application/app/tests/integration/",
    "contract": "generated_application/app/tests/contract/",
    "negative": "generated_application/app/tests/negative/",
    "resilience": "generated_application/app/tests/resilience/",
    "security": "generated_application/app/tests/security/",
    "performance_smoke": "generated_application/app/tests/performance/",
    "replay": "generated_application/app/tests/replay/",
    "audit": "generated_application/app/tests/audit/",
}

REQUIRED_MODULE_DIRS = {
    "domain": "generated_application/app/domain/",
    "application": "generated_application/app/application/",
    "infrastructure": "generated_application/app/infrastructure/",
    "interfaces": "generated_application/app/interfaces/",
    "observability": "generated_application/app/observability/",
    "security": "generated_application/app/security/",
    "tests": "generated_application/app/tests/",
}

REQUIRED_DEEP_FILES = {
    "generated_application/app/domain/entities.py",
    "generated_application/app/domain/value_objects.py",
    "generated_application/app/domain/policies.py",
    "generated_application/app/domain/domain_events.py",
    "generated_application/app/domain/exceptions.py",
    "generated_application/app/application/commands.py",
    "generated_application/app/application/queries.py",
    "generated_application/app/application/services.py",
    "generated_application/app/application/unit_of_work.py",
    "generated_application/app/application/ports.py",
    "generated_application/app/infrastructure/persistence/repositories.py",
    "generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py",
    "generated_application/app/infrastructure/persistence/postgres_unit_of_work.py",
    "generated_application/app/infrastructure/persistence/outbox.py",
    "generated_application/app/infrastructure/persistence/idempotency_store.py",
    "generated_application/app/interfaces/api/main.py",
    "generated_application/app/interfaces/api/schemas.py",
    "generated_application/app/interfaces/api/error_handlers.py",
    "generated_application/app/observability/logging.py",
    "generated_application/app/observability/metrics.py",
    "generated_application/app/observability/tracing.py",
    "generated_application/app/security/pii_redaction.py",
    "generated_application/app/security/input_validation.py",
}

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    PHASE29_POLICY_PATH,
    TEMPLATE_MANIFEST_PATH,
    GENERATOR_PATH,
    ARTIFACT_DIR / "deep_generated_application_regeneration_gate.json",
    ARTIFACT_DIR / "deep_generated_application_regeneration_audit.json",
    ARTIFACT_DIR / "certification_readiness_test_obligation_matrix.json",
    ARTIFACT_DIR / "controlled_regeneration_output_manifest.json",
]

HUMAN_APPROVAL_ACTIONS = {
    "risky self-evolution",
    "destructive actions",
    "merge",
    "tag",
    "release",
    "promotion",
    "live provider calls",
    "certification-related claims",
}

LIVE_INTEGRATION_RISK_TERMS = {
    "requests.",
    "httpx.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "stripe",
    "razorpay",
}

OFFICIAL_CERTIFICATION_CLAIM_PHRASES = {
    "officially certified",
    "official certification granted",
    "npci certified",
    "rbi approved",
    "bank approved",
    "production ready",
    "live payment capability",
}


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    phase29_policy = load_json(PHASE29_POLICY_PATH)
    template_manifest = load_json(TEMPLATE_MANIFEST_PATH)
    gate = load_json(ARTIFACT_DIR / "deep_generated_application_regeneration_gate.json")
    audit = load_json(ARTIFACT_DIR / "deep_generated_application_regeneration_audit.json")
    matrix = load_json(ARTIFACT_DIR / "certification_readiness_test_obligation_matrix.json")
    output_manifest = load_json(ARTIFACT_DIR / "controlled_regeneration_output_manifest.json")
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE30-GA-DEEP-REGENERATION-CERTIFICATION-READINESS-GATE":
        errors.append("Phase 30 policy missing mandatory regeneration gate")
    if policy.get("phase29_generator_output_required") is not True:
        errors.append("Phase 30 policy does not require Phase 29 generator output")
    if policy.get("destructive_workspace_replacement_allowed") is not False:
        errors.append("Phase 30 policy allows destructive generated workspace replacement")
    if phase29_policy.get("required_generator") != str(GENERATOR_PATH):
        errors.append("Phase 29 policy does not identify the deterministic generator")
    if gate.get("phase29_generator_output_required") is not True:
        errors.append("Phase 30 gate does not require Phase 29 generator output")
    if audit.get("controlled_output_strategy") != "temporary_directory_regeneration":
        errors.append("Phase 30 audit does not require controlled temporary regeneration")
    if output_manifest.get("existing_generated_workspace_destructively_replaced") is not False:
        errors.append("Phase 30 output manifest allows destructive replacement")

    policy_obligations = set(policy.get("certification_readiness_test_obligations", []))
    matrix_obligations = set(matrix)
    missing_policy_obligations = sorted(TEST_OBLIGATIONS - policy_obligations)
    missing_matrix_obligations = sorted(TEST_OBLIGATIONS - matrix_obligations)
    if missing_policy_obligations:
        errors.append(f"Policy missing test obligations: {missing_policy_obligations}")
    if missing_matrix_obligations:
        errors.append(f"Lifecycle test matrix missing obligations: {missing_matrix_obligations}")
    if any(not matrix.get(key) for key in TEST_OBLIGATIONS):
        errors.append("Lifecycle test matrix contains an empty required obligation")

    template_dirs = set(template_manifest.get("deep_structure_directories", []))
    missing_test_dirs = sorted(set(TEST_OBLIGATION_DIRS.values()) - template_dirs)
    if missing_test_dirs:
        errors.append(f"Template manifest missing test obligation directories: {missing_test_dirs}")

    policy_approvals = set(policy.get("human_approval_required_for", []))
    missing_approvals = sorted(HUMAN_APPROVAL_ACTIONS - policy_approvals)
    if missing_approvals:
        errors.append(f"Phase 30 policy missing human approval actions: {missing_approvals}")

    for field, expected in {
        "live_provider_calls_allowed": False,
        "real_secrets_allowed": False,
        "deployment_allowed": False,
        "official_certification_claimed": False,
        "official_certification_granted": False,
    }.items():
        if policy.get(field) is not expected:
            errors.append(f"Phase 30 policy has invalid boundary field: {field}")
    if policy.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Phase 30 policy does not preserve certification_ready_not_certified")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 30 policy does not keep ecosystem integrations mocked")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt_text:
            errors.append(f"Phase 30 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "Phase 29 deterministic generator",
        "certification_ready_not_certified",
        "mocked or simulated",
        "human approval",
    ]:
        if phrase not in prompt_text:
            errors.append(f"Phase 30 prompt missing required phrase: {phrase}")


def validate_regenerated_output(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        result = generate(
            run_id="phase30_deep_generated_application_regeneration",
            workspace_root=Path(temp_dir),
            clean=True,
        )
        output_root = result.output_dir / "generated"
        generated_manifest = load_json(result.manifest_path)

        emitted_files = {item.relative_path for item in result.generated_files}
        missing_files = sorted(REQUIRED_DEEP_FILES - emitted_files)
        if missing_files:
            errors.append(f"Regeneration did not emit required deep files: {missing_files}")

        for module, relative_dir in REQUIRED_MODULE_DIRS.items():
            if not (output_root / relative_dir).is_dir():
                errors.append(f"Regeneration did not emit generated module: {module}")
        for obligation, relative_dir in TEST_OBLIGATION_DIRS.items():
            if not (output_root / relative_dir).is_dir():
                errors.append(f"Regeneration did not emit test obligation directory: {obligation}")

        run_phase28_inputs = set(generated_manifest.get("phase28_architecture_depth_inputs", []))
        if not PHASE28_INPUTS.issubset(run_phase28_inputs):
            errors.append("Regeneration manifest does not record Phase 28 inputs")
        if generated_manifest.get("phase29_deep_structure_policy") != str(PHASE29_POLICY_PATH):
            errors.append("Regeneration manifest does not record Phase 29 deep-structure policy")
        if generated_manifest.get("phase29_deep_structure_policy_recorded") is not True:
            errors.append("Regeneration manifest does not assert Phase 29 policy recording")

        generated_obligations = set(
            generated_manifest.get("certification_readiness_test_obligations", [])
        )
        missing_generated_obligations = sorted(TEST_OBLIGATIONS - generated_obligations)
        if missing_generated_obligations:
            errors.append(
                "Regeneration manifest missing test obligations: "
                f"{missing_generated_obligations}"
            )

        generated_approvals = set(generated_manifest.get("risky_actions_require_human_approval", []))
        missing_generated_approvals = sorted(HUMAN_APPROVAL_ACTIONS - generated_approvals)
        if missing_generated_approvals:
            errors.append(
                "Regeneration manifest missing human approval actions: "
                f"{missing_generated_approvals}"
            )

        for field, expected in {
            "real_payment_calls_allowed": False,
            "live_provider_calls_allowed": False,
            "real_secrets_allowed": False,
            "deployment_allowed": False,
            "official_certification_claimed": False,
            "official_certification_granted": False,
        }.items():
            if generated_manifest.get(field) is not expected:
                errors.append(f"Regeneration manifest has invalid boundary field: {field}")
        if generated_manifest.get("certification_boundary") != "certification_ready_not_certified":
            errors.append("Regeneration manifest changed certification boundary")
        if generated_manifest.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
            errors.append("Regeneration manifest enabled non-mocked ecosystem integrations")

        generated_text = "\n".join(
            (output_root / item.relative_path).read_text(encoding="utf-8")
            for item in result.generated_files
        ).lower()
        for risk_term in LIVE_INTEGRATION_RISK_TERMS:
            if risk_term in generated_text:
                errors.append(f"Regenerated application includes live integration risk term: {risk_term}")
        for claim_phrase in OFFICIAL_CERTIFICATION_CLAIM_PHRASES:
            if claim_phrase in generated_text:
                errors.append(
                    f"Regenerated application includes official certification claim: {claim_phrase}"
                )


def validate() -> list[str]:
    errors: list[str] = []
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 30 artifacts: {missing}"]

    validate_static_artifacts(errors)
    validate_regenerated_output(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2))
        return 1
    print("Phase 30 deep generated application regeneration artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
