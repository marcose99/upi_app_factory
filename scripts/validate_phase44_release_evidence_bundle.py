#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.release_evidence_bundle import (  # noqa: E402
    ARTIFACT_DIR,
    AUDIT_PATH,
    BOUNDARY_FALSE_FIELDS,
    BOUNDARY_STATEMENT_PATH,
    EVIDENCE_INDEX_PATH,
    GATE_PATH,
    POLICY_PATH,
    POLICY_SUMMARY_PATH,
    PROMPT_PATH,
    RELEASE_MANIFEST_PATH,
    RUN_INSTRUCTIONS_PATH,
    SUPPLY_CHAIN_PATH,
    TEST_PATH,
    VALIDATION_SUMMARY_PATH,
    VALIDATOR_PATH,
    build_release_evidence_bundle,
    lifecycle_artifact_paths,
    safety_boundaries,
)

GENERATOR_PATH = Path("scripts/generate_phase44_release_evidence_bundle.py")
SERVICE_PATH = Path("factory/operator_portal/release_evidence_bundle.py")

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    VALIDATOR_PATH,
    GENERATOR_PATH,
    SERVICE_PATH,
    TEST_PATH,
    *lifecycle_artifact_paths(),
]

FORBIDDEN_SOURCE_TERMS = [
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "git push",
    "git tag",
    "git merge",
    "twine upload",
    "kubectl apply",
    "terraform apply",
    "secret create",
]

REQUIRED_EVIDENCE_GROUPS = [
    "manifests",
    "policy_and_prompt",
    "validation_evidence",
    "operator_portal_evidence",
    "generated_application_evidence",
    "boundary_and_supply_chain",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_required_files(errors: list[str]) -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        errors.append(f"Missing Phase 44 required files or artifacts: {missing}")


def validate_generated_artifacts_match_builder(errors: list[str]) -> None:
    built = build_release_evidence_bundle()
    expected = {
        RELEASE_MANIFEST_PATH: built["manifest"],
        POLICY_SUMMARY_PATH: built["policy_summary"],
        VALIDATION_SUMMARY_PATH: built["validation_summary"],
        EVIDENCE_INDEX_PATH: built["evidence_index"],
        SUPPLY_CHAIN_PATH: built["supply_chain"],
        GATE_PATH: built["gate"],
        AUDIT_PATH: built["audit"],
    }
    for path, payload in expected.items():
        if load_json(path) != payload:
            errors.append(f"Phase 44 artifact is stale or inconsistent with generator: {path}")
    if RUN_INSTRUCTIONS_PATH.read_text(encoding="utf-8") != built["run_instructions"]:
        errors.append("Phase 44 run instructions are stale or inconsistent with generator")
    if BOUNDARY_STATEMENT_PATH.read_text(encoding="utf-8") != built["boundary_statement"]:
        errors.append("Phase 44 boundary statement is stale or inconsistent with generator")


def validate_policy_prompt_and_bundle(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    manifest = load_json(RELEASE_MANIFEST_PATH)
    policy_summary = load_json(POLICY_SUMMARY_PATH)
    validation_summary = load_json(VALIDATION_SUMMARY_PATH)
    evidence_index = load_json(EVIDENCE_INDEX_PATH)
    supply_chain = load_json(SUPPLY_CHAIN_PATH)
    gate = load_json(GATE_PATH)
    audit = load_json(AUDIT_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    run_instructions = RUN_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    boundary_statement = BOUNDARY_STATEMENT_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE44-RELEASE-EVIDENCE-BUNDLE-GATE":
        errors.append("Phase 44 policy missing mandatory release evidence bundle gate")
    if manifest.get("bundle_format") != "directory_artifacts":
        errors.append("Phase 44 manifest must declare directory_artifacts bundle format")
    if manifest.get("zip_export_created") is not False:
        errors.append("Phase 44 manifest must not create a ZIP export")

    for group in REQUIRED_EVIDENCE_GROUPS:
        if not isinstance(evidence_index.get(group), list) or not evidence_index[group]:
            errors.append(f"Phase 44 evidence index missing populated group: {group}")

    for artifact, name in [
        (policy, "policy"),
        (manifest, "manifest"),
        (policy_summary.get("boundary_controls", {}), "policy summary boundaries"),
        (validation_summary, "validation summary"),
        (supply_chain, "supply-chain evidence"),
        (gate, "gate"),
        (audit, "audit"),
    ]:
        validate_boundary_payload(artifact, name, errors)

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if f"{{{{ include: {contract_path} }}}}" not in prompt:
            errors.append(f"Phase 44 prompt does not inherit contract: {contract_path}")

    for phrase in [
        "manifests",
        "policy summaries",
        "validation summaries",
        "evidence index",
        "run instructions",
        "boundary statements",
    ]:
        if phrase not in " ".join(manifest.get("included_sections", [])):
            errors.append(f"Phase 44 manifest missing required section: {phrase}")

    for phrase in [
        "certification_ready_not_certified",
        "does not claim official certification",
        "local-readiness evidence",
        "mocked or simulated",
        "No live provider calls are enabled",
        "does not create real secrets",
        "does not deploy",
    ]:
        if phrase.lower() not in (boundary_statement + run_instructions).lower():
            errors.append(f"Phase 44 boundary/run instructions missing: {phrase}")


def validate_boundary_payload(
    payload: dict[str, Any],
    name: str,
    errors: list[str],
) -> None:
    if payload.get("certification_boundary") != "certification_ready_not_certified":
        errors.append(f"Phase 44 {name} changed certification boundary")
    for field in BOUNDARY_FALSE_FIELDS:
        if payload.get(field) is not False:
            errors.append(f"Phase 44 {name} has invalid boundary field: {field}")
    if payload.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append(f"Phase 44 {name} does not keep ecosystem integrations mocked")
    scope = str(payload.get("production_readiness_scope", ""))
    if "local-readiness" not in scope or "not_claimed" not in scope:
        errors.append(f"Phase 44 {name} lacks local-readiness-only production scope")


def validate_supply_chain_status(errors: list[str]) -> None:
    supply_chain = load_json(SUPPLY_CHAIN_PATH)
    status = supply_chain.get("status")
    available_tools = supply_chain.get("available_tools")
    if status not in {"available", "unavailable"}:
        errors.append("Phase 44 supply-chain evidence has invalid status")
    if status == "unavailable" and available_tools:
        errors.append("Phase 44 supply-chain evidence says unavailable but lists tools")
    if supply_chain.get("sbom_generated") is not False:
        errors.append("Phase 44 supply-chain evidence must not claim generated SBOM output")
    if supply_chain.get("external_network_calls_allowed") is not False:
        errors.append("Phase 44 supply-chain evidence must not allow external network calls")


def validate_no_forbidden_runtime_actions(errors: list[str]) -> None:
    source_paths = [SERVICE_PATH, GENERATOR_PATH]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source:
            errors.append(f"Phase 44 source includes forbidden runtime term: {term}")

    text_artifacts = [
        RUN_INSTRUCTIONS_PATH,
        BOUNDARY_STATEMENT_PATH,
        PROMPT_PATH,
        POLICY_PATH,
        RELEASE_MANIFEST_PATH,
        POLICY_SUMMARY_PATH,
        VALIDATION_SUMMARY_PATH,
        EVIDENCE_INDEX_PATH,
        SUPPLY_CHAIN_PATH,
        GATE_PATH,
        AUDIT_PATH,
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in text_artifacts)
    forbidden_claims = [
        "officially certified",
        "certification granted",
        "production ready",
        "live payment enabled",
        "real provider enabled",
    ]
    for claim in forbidden_claims:
        if claim in joined.lower():
            errors.append(f"Phase 44 artifacts include forbidden claim: {claim}")

    zip_files = list(ARTIFACT_DIR.glob("*.zip"))
    if zip_files:
        errors.append(f"Phase 44 lifecycle artifacts include forbidden ZIP files: {zip_files}")


def validate_service_boundaries(errors: list[str]) -> None:
    validate_boundary_payload(safety_boundaries(), "service boundaries", errors)


def validate() -> list[str]:
    errors: list[str] = []
    validate_required_files(errors)
    if errors:
        return errors
    validate_generated_artifacts_match_builder(errors)
    validate_policy_prompt_and_bundle(errors)
    validate_supply_chain_status(errors)
    validate_service_boundaries(errors)
    validate_no_forbidden_runtime_actions(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 44 release evidence bundle validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
