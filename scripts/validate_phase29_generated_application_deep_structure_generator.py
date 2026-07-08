#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, cast

from factory.generators.mock_dispute_app_generator import generate


APP_ID = "upi_dispute_resolution"
POLICY_PATH = Path("policies/phase29_generated_application_deep_structure_policy.json")
PROMPT_PATH = Path("prompts/phase29/generated_application_deep_structure_prompt.md")
TEMPLATE_MANIFEST_PATH = Path("factory/templates/mock_dispute_app/template_manifest.v1.json")
GENERATOR_PATH = Path("factory/generators/mock_dispute_app_generator.py")
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase29"

PHASE28_INPUTS = {
    "factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json",
    "policies/phase28_generated_application_architecture_depth_policy.json",
    "prompts/phase28/generated_application_architecture_depth_prompt.md",
}

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    TEMPLATE_MANIFEST_PATH,
    GENERATOR_PATH,
    ARTIFACT_DIR / "deep_structure_generator_gate.json",
    ARTIFACT_DIR / "deep_structure_generator_audit.json",
]

REQUIRED_DEEP_STRUCTURE_FILES = {
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

REQUIRED_DEEP_STRUCTURE_DIRS = {
    "generated_application/",
    "generated_application/app/",
    "generated_application/app/domain/",
    "generated_application/app/application/",
    "generated_application/app/infrastructure/persistence/migrations/",
    "generated_application/app/interfaces/api/routers/",
    "generated_application/app/interfaces/cli/",
    "generated_application/app/interfaces/workers/",
    "generated_application/app/tests/unit/",
    "generated_application/app/tests/integration/",
    "generated_application/app/tests/contract/",
    "generated_application/app/tests/negative/",
    "generated_application/app/tests/resilience/",
    "generated_application/app/tests/security/",
    "generated_application/app/tests/performance/",
}

CAPABILITY_TERMS = {
    "DisputeState",
    "ALLOWED_TRANSITIONS",
    "DisputeService",
    "UnitOfWork",
    "SqliteUnitOfWork",
    "SqliteIdempotencyStore",
    "SqliteOutbox",
    "CreateDisputeRequest",
    "domain_error_handler",
    "redact_upi",
    "reject_live_endpoint",
    "Metrics",
    "local_span",
}


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def contains_case_insensitive(text: str, expected: str) -> bool:
    return expected.lower() in text.lower()


def validate() -> list[str]:
    errors: list[str] = []
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 29 artifacts: {missing}"]

    policy = load_json(POLICY_PATH)
    manifest = load_json(TEMPLATE_MANIFEST_PATH)
    gate = load_json(ARTIFACT_DIR / "deep_structure_generator_gate.json")
    audit = load_json(ARTIFACT_DIR / "deep_structure_generator_audit.json")
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    generator_text = GENERATOR_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE29-GA-DEEP-STRUCTURE-GENERATOR-GATE":
        errors.append("Policy missing Phase 29 gate")
    if policy.get("phase28_blueprint_required_as_generator_input") is not True:
        errors.append("Policy does not require Phase 28 blueprint as generator input")
    if policy.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Policy does not preserve certification-ready-not-certified")
    if policy.get("official_certification_claimed") is not False:
        errors.append("Policy allows official certification claims")
    if policy.get("live_provider_calls_allowed") is not False:
        errors.append("Policy allows live provider calls")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Policy does not keep external ecosystem integrations mocked")

    if gate.get("phase28_architecture_depth_inputs_required") is not True:
        errors.append("Gate does not require Phase 28 architecture-depth inputs")
    if audit.get("phase28_architecture_depth_inputs_required") is not True:
        errors.append("Audit does not require Phase 28 architecture-depth inputs")
    if audit.get("risky_self_evolution_requires_human_approval") is not True:
        errors.append("Audit does not preserve human approval for risky self-evolution")

    manifest_phase28_inputs = set(manifest.get("phase28_architecture_depth_inputs", []))
    missing_phase28_inputs = sorted(PHASE28_INPUTS - manifest_phase28_inputs)
    if missing_phase28_inputs:
        errors.append(f"Template manifest missing Phase 28 inputs: {missing_phase28_inputs}")

    manifest_files = set(manifest.get("template_files", []))
    missing_deep_files = sorted(REQUIRED_DEEP_STRUCTURE_FILES - manifest_files)
    if missing_deep_files:
        errors.append(f"Template manifest missing deep-structure files: {missing_deep_files}")

    manifest_dirs = set(manifest.get("deep_structure_directories", []))
    missing_deep_dirs = sorted(REQUIRED_DEEP_STRUCTURE_DIRS - manifest_dirs)
    if missing_deep_dirs:
        errors.append(f"Template manifest missing deep-structure directories: {missing_deep_dirs}")

    for phrase in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
        "Phase 28 architecture-depth blueprint",
        "certification_ready_not_certified",
        "human approval",
    ]:
        if phrase not in prompt_text:
            errors.append(f"Prompt missing required inherited contract or boundary phrase: {phrase}")

    for phrase in [
        "PHASE28_BLUEPRINT_PATH",
        "phase28_architecture_depth_inputs",
        "PHASE29_POLICY_PATH",
        "create_deep_structure_directories",
        "mocked_or_simulated_only",
        "certification_ready_not_certified",
    ]:
        if phrase not in generator_text:
            errors.append(f"Generator missing required Phase 29 enforcement phrase: {phrase}")

    template_text = "\n".join(
        (Path("factory/templates/mock_dispute_app") / path).read_text(encoding="utf-8")
        for path in REQUIRED_DEEP_STRUCTURE_FILES
    )
    missing_terms = sorted(term for term in CAPABILITY_TERMS if term not in template_text)
    if missing_terms:
        errors.append(f"Deep-structure templates missing capability terms: {missing_terms}")
    for prohibited in ["requests.", "httpx.", "boto3", "google.cloud", "stripe", "razorpay"]:
        if prohibited in template_text:
            errors.append(f"Deep-structure templates include live-integration risk term: {prohibited}")

    with tempfile.TemporaryDirectory() as temp_dir:
        result = generate(run_id="phase29_validator", workspace_root=Path(temp_dir), clean=True)
        output_root = result.output_dir / "generated"
        emitted_files = {item.relative_path for item in result.generated_files}
        missing_emitted_files = sorted(REQUIRED_DEEP_STRUCTURE_FILES - emitted_files)
        if missing_emitted_files:
            errors.append(f"Generator did not emit deep-structure files: {missing_emitted_files}")
        for relative_dir in REQUIRED_DEEP_STRUCTURE_DIRS:
            if not (output_root / relative_dir).is_dir():
                errors.append(f"Generator did not create deep-structure directory: {relative_dir}")

        run_manifest = load_json(result.manifest_path)
        run_phase28_inputs = set(run_manifest.get("phase28_architecture_depth_inputs", []))
        if not PHASE28_INPUTS.issubset(run_phase28_inputs):
            errors.append("Generation manifest does not record Phase 28 architecture-depth inputs")
        if run_manifest.get("live_provider_calls_allowed") is not False:
            errors.append("Generation manifest allows live provider calls")
        if run_manifest.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
            errors.append("Generation manifest does not preserve mocked ecosystem boundary")
        if run_manifest.get("certification_boundary") != "certification_ready_not_certified":
            errors.append("Generation manifest does not preserve certification-ready-not-certified")

    for phrase in [
        "certification-ready-not-certified",
        "External UPI rails",
        "mocked or simulated",
        "Risky self-evolution",
    ]:
        if not contains_case_insensitive(prompt_text, phrase):
            errors.append(f"Prompt missing required capability phrase: {phrase}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2))
        return 1
    print("Phase 29 generated application deep-structure generator artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
