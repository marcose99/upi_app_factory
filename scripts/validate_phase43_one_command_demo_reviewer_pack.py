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

from factory.operator_portal.demo_reviewer_pack import (  # noqa: E402
    SAFE_AUTOMATED_COMMAND_IDS,
    STAGED_COMMANDS,
    build_staged_command_report,
    safety_boundaries,
)


APP_ID = "upi_dispute_resolution"
POLICY_PATH = Path("policies/phase43_one_command_demo_reviewer_pack_policy.json")
PROMPT_PATH = Path("prompts/phase43/one_command_demo_reviewer_pack_prompt.md")
SCRIPT_PATH = Path("scripts/run_phase43_one_command_demo_reviewer_pack.py")
SERVICE_PATH = Path("factory/operator_portal/demo_reviewer_pack.py")
TEST_PATH = Path("tests/test_phase43_one_command_demo_reviewer_pack.py")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase43"
)
REVIEWER_PACK_PATH = ARTIFACT_DIR / "reviewer_pack.md"
MANIFEST_PATH = ARTIFACT_DIR / "one_command_demo_manifest.json"
GATE_PATH = ARTIFACT_DIR / "demo_reviewer_pack_gate.json"
AUDIT_PATH = ARTIFACT_DIR / "demo_reviewer_pack_audit.json"

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    SCRIPT_PATH,
    SERVICE_PATH,
    TEST_PATH,
    REVIEWER_PACK_PATH,
    MANIFEST_PATH,
    GATE_PATH,
    AUDIT_PATH,
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
]

BOUNDARY_FALSE_FIELDS = [
    "official_certification_claimed",
    "official_certification_granted",
    "production_readiness_claimed",
    "live_provider_calls_allowed",
    "real_secrets_allowed",
    "deployment_allowed",
    "merge_allowed",
    "tag_allowed",
    "push_allowed",
    "real_payment_rails_enabled",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_required_files(errors: list[str]) -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        errors.append(f"Missing Phase 43 required files: {missing}")


def validate_policy_prompt_and_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    manifest = load_json(MANIFEST_PATH)
    gate = load_json(GATE_PATH)
    audit = load_json(AUDIT_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    reviewer_pack = REVIEWER_PACK_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE43-ONE-COMMAND-DEMO-REVIEWER-PACK-GATE":
        errors.append("Phase 43 policy missing mandatory one-command demo gate")
    if manifest.get("default_command") != "make phase43-demo-reviewer-pack":
        errors.append("Phase 43 manifest does not define the one-command demo target")
    if manifest.get("staged_command_mode") is not True:
        errors.append("Phase 43 manifest does not use staged command mode")

    artifacts = [
        (policy, "policy"),
        (manifest, "manifest"),
        (gate, "gate"),
        (audit, "audit"),
    ]
    for artifact, name in artifacts:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 43 {name} changed certification boundary")
        for field in BOUNDARY_FALSE_FIELDS:
            if artifact.get(field) is not False:
                errors.append(f"Phase 43 {name} has invalid boundary field: {field}")
        if artifact.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
            errors.append(f"Phase 43 {name} does not keep ecosystem integrations mocked")
        scope = str(artifact.get("production_readiness_scope", ""))
        if "local-readiness" not in scope:
            errors.append(f"Phase 43 {name} lacks local-readiness-only production scope")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if f"{{{{ include: {contract_path} }}}}" not in prompt:
            errors.append(f"Phase 43 prompt does not inherit contract: {contract_path}")

    for required_phrase in [
        "what the factory does",
        "how to run",
        "evidence",
        "mocked or simulated",
        "certification_ready_not_certified",
        "Known Limitations",
    ]:
        if required_phrase.lower() not in reviewer_pack.lower():
            errors.append(f"Reviewer pack missing required content: {required_phrase}")


def validate_one_command_behavior(errors: list[str]) -> None:
    report = build_staged_command_report()
    if report.get("status") != "staged_commands":
        errors.append("Phase 43 default report does not print staged commands")
    if report.get("one_command") != "make phase43-demo-reviewer-pack":
        errors.append("Phase 43 default report does not expose the Makefile command")

    command_results = report.get("staged_commands")
    if not isinstance(command_results, list) or not command_results:
        errors.append("Phase 43 default report does not list staged commands")
    else:
        returned_ids = {
            entry.get("command_id") for entry in command_results if isinstance(entry, dict)
        }
        expected_ids = {command.command_id for command in STAGED_COMMANDS}
        if returned_ids != expected_ids:
            errors.append("Phase 43 staged command IDs do not match the governed set")

    if set(report.get("safe_automated_command_ids", [])) != set(SAFE_AUTOMATED_COMMAND_IDS):
        errors.append("Phase 43 safe automated command list changed unexpectedly")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"Phase 43 one-command script failed: {result.stdout}{result.stderr}")
        return
    payload = json.loads(result.stdout)
    if payload.get("status") != "staged_commands":
        errors.append("Phase 43 one-command script did not print staged commands by default")


def validate_safety_boundaries(errors: list[str]) -> None:
    boundaries = safety_boundaries()
    if boundaries.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Phase 43 service changed certification-ready-not-certified boundary")
    for field in BOUNDARY_FALSE_FIELDS:
        if boundaries.get(field) is not False:
            errors.append(f"Phase 43 service has invalid safety boundary: {field}")
    if boundaries.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 43 service does not keep external integrations mocked")
    if "local-readiness" not in str(boundaries.get("production_readiness_scope", "")):
        errors.append("Phase 43 service does not scope readiness to local-readiness checks")


def validate_no_forbidden_runtime_actions(errors: list[str]) -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8") + SCRIPT_PATH.read_text(encoding="utf-8")
    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source:
            errors.append(f"Phase 43 source includes forbidden runtime term: {term}")

    for command in STAGED_COMMANDS:
        command_text = " ".join(command.argv)
        for forbidden in ["git push", "git tag", "git merge", "deploy", "secret create"]:
            if forbidden in command_text:
                errors.append(f"Phase 43 staged command enables forbidden action: {command_text}")

    zip_files = list(ARTIFACT_DIR.glob("*.zip"))
    if zip_files:
        errors.append(f"Phase 43 lifecycle artifacts include forbidden ZIP files: {zip_files}")


def validate() -> list[str]:
    errors: list[str] = []
    validate_required_files(errors)
    if errors:
        return errors
    validate_policy_prompt_and_artifacts(errors)
    validate_one_command_behavior(errors)
    validate_safety_boundaries(errors)
    validate_no_forbidden_runtime_actions(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 43 one-command demo reviewer pack validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
