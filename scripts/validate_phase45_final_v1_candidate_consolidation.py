#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.final_v1_candidate_consolidation import (  # noqa: E402
    ARTIFACT_DIR,
    ARCHITECTURE_SUMMARY_PATH,
    BOUNDARY_FALSE_FIELDS,
    FINAL_EVIDENCE_INDEX_PATH,
    FINAL_MANIFEST_PATH,
    FINAL_RUNBOOK_PATH,
    GENERATED_APP_SUMMARY_PATH,
    GENERATOR_PATH,
    LIFECYCLE_AUDIT_PATH,
    LIMITATION_STATEMENT_PATH,
    LOCAL_DEMO_INSTRUCTIONS_PATH,
    NEXT_ROADMAP_PATH,
    OPERATOR_PORTAL_SUMMARY_PATH,
    POLICY_PATH,
    PREPARED_FUTURE_TAG,
    PROMPT_PATH,
    README_PATH,
    RELEASE_GATE_PATH,
    TEST_PATH,
    VALIDATION_SUMMARY_PATH,
    VALIDATOR_PATH,
    build_final_v1_candidate_bundle,
    lifecycle_artifact_paths,
    safety_boundaries,
)

SERVICE_PATH = Path("factory/operator_portal/final_v1_candidate_consolidation.py")

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    VALIDATOR_PATH,
    GENERATOR_PATH,
    TEST_PATH,
    README_PATH,
    SERVICE_PATH,
    *lifecycle_artifact_paths(),
]

FORBIDDEN_SOURCE_TERMS = [
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "twine upload",
    "kubectl apply",
    "terraform apply",
    "secret create",
]

SUMMARY_PATHS = [
    FINAL_RUNBOOK_PATH,
    ARCHITECTURE_SUMMARY_PATH,
    OPERATOR_PORTAL_SUMMARY_PATH,
    GENERATED_APP_SUMMARY_PATH,
    LIMITATION_STATEMENT_PATH,
    NEXT_ROADMAP_PATH,
    LOCAL_DEMO_INSTRUCTIONS_PATH,
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_required_files(errors: list[str]) -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        errors.append(f"Missing Phase 45 required files or artifacts: {missing}")


def validate_generated_artifacts_match_builder(errors: list[str]) -> None:
    built = build_final_v1_candidate_bundle()
    expected_json = {
        FINAL_MANIFEST_PATH: built["manifest"],
        RELEASE_GATE_PATH: built["release_gate"],
        VALIDATION_SUMMARY_PATH: built["validation_summary"],
        FINAL_EVIDENCE_INDEX_PATH: built["final_evidence_index"],
        LIFECYCLE_AUDIT_PATH: built["lifecycle_audit"],
    }
    for path, payload in expected_json.items():
        if load_json(path) != payload:
            errors.append(f"Phase 45 artifact is stale or inconsistent with builder: {path}")

    expected_text = {
        FINAL_RUNBOOK_PATH: built["final_runbook"],
        ARCHITECTURE_SUMMARY_PATH: built["architecture_summary"],
        OPERATOR_PORTAL_SUMMARY_PATH: built["operator_portal_summary"],
        GENERATED_APP_SUMMARY_PATH: built["generated_application_summary"],
        LIMITATION_STATEMENT_PATH: built["limitation_statement"],
        NEXT_ROADMAP_PATH: built["next_roadmap"],
        LOCAL_DEMO_INSTRUCTIONS_PATH: built["local_demo_instructions"],
    }
    for path, text in expected_text.items():
        if path.read_text(encoding="utf-8") != text:
            errors.append(f"Phase 45 text artifact is stale or inconsistent: {path}")


def validate_boundary_payload(
    payload: dict[str, Any],
    name: str,
    errors: list[str],
) -> None:
    if payload.get("certification_boundary") != "certification_ready_not_certified":
        errors.append(f"Phase 45 {name} changed certification boundary")
    for field in BOUNDARY_FALSE_FIELDS:
        if payload.get(field) is not False:
            errors.append(f"Phase 45 {name} has invalid boundary field: {field}")
    if payload.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append(f"Phase 45 {name} does not keep ecosystem integrations mocked")
    scope = str(payload.get("production_readiness_scope", ""))
    if "local-readiness" not in scope or "not_claimed" not in scope:
        errors.append(f"Phase 45 {name} lacks local-readiness-only production scope")


def validate_policy_prompt_readme_and_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    manifest = load_json(FINAL_MANIFEST_PATH)
    gate = load_json(RELEASE_GATE_PATH)
    validation = load_json(VALIDATION_SUMMARY_PATH)
    evidence = load_json(FINAL_EVIDENCE_INDEX_PATH)
    audit = load_json(LIFECYCLE_AUDIT_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE45-FINAL-V1-CANDIDATE-GATE":
        errors.append("Phase 45 policy missing mandatory final v1 candidate gate")
    if manifest.get("prepared_future_tag") != PREPARED_FUTURE_TAG:
        errors.append("Phase 45 manifest missing prepared future tag value")
    if manifest.get("future_tag_created") is not False:
        errors.append("Phase 45 manifest must not claim future tag creation")
    if gate.get("automatic_release_actions_enabled") is not False:
        errors.append("Phase 45 release gate must not enable automatic release actions")

    for artifact, name in [
        (policy, "policy"),
        (manifest, "manifest"),
        (gate, "release gate"),
        (validation, "validation summary"),
        (evidence, "final evidence index"),
        (audit, "lifecycle audit"),
    ]:
        validate_boundary_payload(artifact, name, errors)

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if f"{{{{ include: {contract_path} }}}}" not in prompt:
            errors.append(f"Phase 45 prompt does not inherit contract: {contract_path}")

    for group in [
        "final_candidate_artifacts",
        "policy_and_prompt",
        "validators_and_tests",
        "operator_portal_evidence",
        "generated_application_evidence",
        "release_evidence_bundle",
    ]:
        if not isinstance(evidence.get(group), list) or not evidence[group]:
            errors.append(f"Phase 45 final evidence index missing populated group: {group}")

    for phrase in [
        "Phase 45",
        "certification_ready_not_certified",
        "local-readiness",
        "mocked or simulated",
        PREPARED_FUTURE_TAG,
    ]:
        if phrase.lower() not in readme.lower():
            errors.append(f"README missing Phase 45 update phrase: {phrase}")


def validate_summary_documents(errors: list[str]) -> None:
    joined = "\n".join(path.read_text(encoding="utf-8") for path in SUMMARY_PATHS)
    required_phrases = [
        "certification_ready_not_certified",
        "local-readiness",
        "mocked or simulated",
        "No real secrets",
        "No live provider calls",
        "does not claim",
    ]
    for phrase in required_phrases:
        if phrase.lower() not in joined.lower():
            errors.append(f"Phase 45 summaries missing required boundary phrase: {phrase}")


def validate_no_forbidden_runtime_actions(errors: list[str]) -> None:
    source_paths = [SERVICE_PATH, GENERATOR_PATH]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source:
            errors.append(f"Phase 45 source includes forbidden runtime term: {term}")

    text_artifacts = [
        POLICY_PATH,
        PROMPT_PATH,
        FINAL_MANIFEST_PATH,
        RELEASE_GATE_PATH,
        VALIDATION_SUMMARY_PATH,
        FINAL_EVIDENCE_INDEX_PATH,
        LIFECYCLE_AUDIT_PATH,
        *SUMMARY_PATHS,
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in text_artifacts).lower()
    forbidden_claims = [
        "officially certified",
        "certification granted",
        "production ready",
        "live payment enabled",
        "real provider enabled",
    ]
    for claim in forbidden_claims:
        if claim in joined:
            errors.append(f"Phase 45 artifacts include forbidden claim: {claim}")

    zip_files = list(ARTIFACT_DIR.glob("*.zip"))
    if zip_files:
        errors.append(f"Phase 45 lifecycle artifacts include forbidden ZIP files: {zip_files}")


def validate_service_boundaries(errors: list[str]) -> None:
    validate_boundary_payload(safety_boundaries(), "service boundaries", errors)


def validate() -> list[str]:
    errors: list[str] = []
    validate_required_files(errors)
    if errors:
        return errors
    validate_generated_artifacts_match_builder(errors)
    validate_policy_prompt_readme_and_artifacts(errors)
    validate_summary_documents(errors)
    validate_service_boundaries(errors)
    validate_no_forbidden_runtime_actions(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "phase": "phase45_final_v1_candidate_consolidation",
                "passed": True,
                "certification_boundary": "certification_ready_not_certified",
                "prepared_future_tag": PREPARED_FUTURE_TAG,
                "future_tag_created": False,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
