#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.prerequisite_artifacts import materialize_clean_clone_test_evidence  # noqa: E402
APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase28"
BLUEPRINT_PATH = (
    Path("factory_governance/generated_application_architecture_depth")
    / "phase28_architecture_depth_blueprint.v1.json"
)
SCHEMA_PATH = (
    Path("factory_governance/generated_application_architecture_depth")
    / "phase28_architecture_depth_blueprint.schema.json"
)
POLICY_PATH = Path("policies/phase28_generated_application_architecture_depth_policy.json")
PROMPT_PATH = Path("prompts/phase28/generated_application_architecture_depth_prompt.md")
DOC_PATH = Path("docs/phase28_generated_application_architecture_depth_blueprint.md")

REQUIRED_FILES = [
    BLUEPRINT_PATH,
    SCHEMA_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    DOC_PATH,
    Path("scripts/validate_phase28_generated_application_architecture_depth_blueprint.py"),
    Path("tests/test_phase28_generated_application_architecture_depth_blueprint.py"),
    ARTIFACT_DIR / "architecture_depth_artifact_manifest.json",
    ARTIFACT_DIR / "architecture_depth_gate.json",
    ARTIFACT_DIR / "architecture_conformance_expectations.json",
    ARTIFACT_DIR / "test_obligation_matrix.json",
    ARTIFACT_DIR / "self_evolution_backlog_policy.json",
    ARTIFACT_DIR / "certification_boundary.json",
    ARTIFACT_DIR / "phase28_architecture_depth_audit.json",
]

REQUIRED_ARCHITECTURE_ARTIFACTS = {
    "architecture_blueprint.md",
    "domain_model.md",
    "bounded_contexts.md",
    "dispute_state_machine.md",
    "api_contracts.md",
    "data_contracts.md",
    "security_model.md",
    "observability_model.md",
    "test_obligation_matrix.md",
    "certification_readiness_boundary.md",
}
SELF_EVOLUTION_ARTIFACTS = {"self_evolution_backlog.json", "self_evolution_backlog.md"}

TARGET_STRUCTURE_PATHS = {
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
    "generated_application/app/infrastructure/persistence/migrations/",
    "generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py",
    "generated_application/app/infrastructure/persistence/postgres_unit_of_work.py",
    "generated_application/app/infrastructure/persistence/outbox.py",
    "generated_application/app/infrastructure/persistence/idempotency_store.py",
    "generated_application/app/interfaces/api/main.py",
    "generated_application/app/interfaces/api/routers/",
    "generated_application/app/interfaces/api/schemas.py",
    "generated_application/app/interfaces/api/error_handlers.py",
    "generated_application/app/interfaces/cli/",
    "generated_application/app/interfaces/workers/",
    "generated_application/app/observability/logging.py",
    "generated_application/app/observability/metrics.py",
    "generated_application/app/observability/tracing.py",
    "generated_application/app/security/pii_redaction.py",
    "generated_application/app/security/input_validation.py",
    "generated_application/app/tests/unit/",
    "generated_application/app/tests/integration/",
    "generated_application/app/tests/contract/",
    "generated_application/app/tests/negative/",
    "generated_application/app/tests/resilience/",
    "generated_application/app/tests/security/",
    "generated_application/app/tests/performance/",
}

TEST_OBLIGATION_KEYS = {
    "positive",
    "negative",
    "contract",
    "security",
    "resilience",
    "replay",
    "audit",
    "performance_smoke",
}


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def contains_case_insensitive(text: str, expected: str) -> bool:
    return expected.lower() in text.lower()


def validate() -> list[str]:
    materialization = materialize_clean_clone_test_evidence(PROJECT_ROOT, include_phases={"phase28"})
    if materialization["status"] != "PASSED":
        return [
            "Unable to materialize Phase 28 prerequisite lifecycle artifacts: "
            f"{materialization['errors']}"
        ]
    errors: list[str] = []
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 28 artifacts: {missing}"]

    blueprint = load_json(BLUEPRINT_PATH)
    policy = load_json(POLICY_PATH)
    manifest = load_json(ARTIFACT_DIR / "architecture_depth_artifact_manifest.json")
    gate = load_json(ARTIFACT_DIR / "architecture_depth_gate.json")
    conformance = load_json(ARTIFACT_DIR / "architecture_conformance_expectations.json")
    matrix = load_json(ARTIFACT_DIR / "test_obligation_matrix.json")
    self_evolution = load_json(ARTIFACT_DIR / "self_evolution_backlog_policy.json")
    boundary = load_json(ARTIFACT_DIR / "certification_boundary.json")
    audit = load_json(ARTIFACT_DIR / "phase28_architecture_depth_audit.json")
    prompt_text = read_text(PROMPT_PATH)
    doc_text = read_text(DOC_PATH)

    if blueprint.get("status") != "ARCHITECTURE_DEPTH_BLUEPRINT_REQUIRED":
        errors.append("Blueprint status does not require architecture depth")

    artifact_names = set(blueprint.get("required_architecture_depth_artifacts", []))
    manifest_names = set(manifest.get("required_architecture_depth_artifacts", []))
    missing_artifacts = sorted(REQUIRED_ARCHITECTURE_ARTIFACTS - artifact_names)
    if missing_artifacts:
        errors.append(f"Blueprint missing required artifact names: {missing_artifacts}")
    if not artifact_names.intersection(SELF_EVOLUTION_ARTIFACTS):
        errors.append("Blueprint missing self-evolution backlog artifact")
    if not manifest_names.issuperset(REQUIRED_ARCHITECTURE_ARTIFACTS):
        errors.append("Lifecycle manifest missing required architecture-depth artifacts")

    blueprint_gate = blueprint.get("architecture_depth_gate", {})
    if blueprint_gate.get("gate_id") != "PHASE28-GA-ARCHITECTURE-DEPTH-GATE":
        errors.append("Blueprint architecture-depth gate id is missing")
    if blueprint_gate.get("required_before_application_generation_success") is not True:
        errors.append("Architecture-depth gate is not required before generation success")
    if gate.get("required_before_application_generation_success") is not True:
        errors.append("Lifecycle gate is not required before generation success")
    if policy.get("required_before_generation_success") is not True:
        errors.append("Policy does not require architecture-depth before generation success")

    target_structure = set(blueprint.get("target_generated_application_structure", []))
    missing_structure = sorted(TARGET_STRUCTURE_PATHS - target_structure)
    if missing_structure:
        errors.append(f"Blueprint missing target structure paths: {missing_structure}")

    for phrase in [
        "Generate architecture first",
        "before expanding business logic",
        "mocked or simulated",
        "certification_ready_not_certified",
    ]:
        if not contains_case_insensitive(prompt_text, phrase):
            errors.append(f"Prompt missing architecture-first phrase: {phrase}")

    if boundary.get("official_certification_claimed") is not False:
        errors.append("Certification boundary allows official certification claims")
    if audit.get("official_certification_claimed") is not False:
        errors.append("Audit claims official certification")
    if audit.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Audit does not preserve certification-ready-not-certified boundary")

    if boundary.get("live_provider_calls_allowed") is not False:
        errors.append("Boundary allows live provider calls")
    if boundary.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Boundary does not keep external integrations mocked/simulated")
    if audit.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Audit does not keep external integrations mocked/simulated")

    if self_evolution.get("may_propose_improvements") is not True:
        errors.append("Self-evolution cannot propose improvements")
    if self_evolution.get("risky_changes_require_human_approval") is not True:
        errors.append("Risky self-evolution changes are not human-approved")

    matrix_keys = set(matrix)
    missing_matrix_keys = sorted(TEST_OBLIGATION_KEYS - matrix_keys)
    if missing_matrix_keys:
        errors.append(f"Test obligation matrix missing keys: {missing_matrix_keys}")
    for key in TEST_OBLIGATION_KEYS:
        if not matrix.get(key):
            errors.append(f"Test obligation matrix entry is empty: {key}")

    import_expectations = conformance.get("import_boundary_expectations", [])
    state_expectations = conformance.get("state_machine_expectations", [])
    if not any("domain layer" in item for item in import_expectations):
        errors.append("Import-boundary expectations do not constrain domain imports")
    if not any("interfaces layer" in item for item in import_expectations):
        errors.append("Import-boundary expectations do not constrain interface imports")
    if not any("invalid transitions" in item for item in state_expectations):
        errors.append("State-machine expectations do not cover invalid transitions")
    if not any("idempotent replay" in item for item in state_expectations):
        errors.append("State-machine expectations do not cover idempotent replay")

    for phrase in [
        "PHASE28-GA-ARCHITECTURE-DEPTH-GATE",
        "positive, negative, contract, security, resilience, replay, audit, and performance-smoke",
        "does not certify",
    ]:
        if not contains_case_insensitive(doc_text, phrase):
            errors.append(f"Documentation missing required phrase: {phrase}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2))
        return 1
    print("Phase 28 generated application architecture-depth blueprint artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
