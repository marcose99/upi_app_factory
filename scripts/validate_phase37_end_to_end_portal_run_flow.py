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

from factory.operator_portal.end_to_end_run_flow import (  # noqa: E402
    SAFETY_BOUNDARIES,
    EndToEndPortalRunFlowService,
)


APP_ID = "upi_dispute_resolution"
SERVICE_PATH = Path("factory/operator_portal/end_to_end_run_flow.py")
RUN_SCRIPT_PATH = Path("scripts/run_phase37_end_to_end_portal_run_flow.py")
POLICY_PATH = Path("policies/phase37_end_to_end_portal_run_flow_policy.json")
PROMPT_PATH = Path("prompts/phase37/end_to_end_portal_run_flow_prompt.md")
TEST_PATH = Path("tests/test_phase37_end_to_end_portal_run_flow.py")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase37"
)

REQUIRED_STAGE_STATUSES = {
    "intake_requirements_available",
    "generation_command",
    "export_bundle_ready",
    "validation_dry_run_ready",
    "validation_run",
    "evidence_dashboard_updated",
    "download_available",
}
REQUIRED_FILES = [
    SERVICE_PATH,
    RUN_SCRIPT_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    TEST_PATH,
    ARTIFACT_DIR / "end_to_end_portal_run_flow_gate.json",
    ARTIFACT_DIR / "end_to_end_portal_run_flow_audit.json",
    ARTIFACT_DIR / "end_to_end_portal_run_flow_manifest.json",
]
FORBIDDEN_SOURCE_TERMS = [
    "shell=True",
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "git push",
    "git tag",
    "git merge",
    "api_key",
    "client_secret",
    "BEGIN PRIVATE KEY",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "end_to_end_portal_run_flow_gate.json")
    audit = load_json(ARTIFACT_DIR / "end_to_end_portal_run_flow_audit.json")
    manifest = load_json(ARTIFACT_DIR / "end_to_end_portal_run_flow_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    combined_source = "\n".join(
        [
            SERVICE_PATH.read_text(encoding="utf-8"),
            RUN_SCRIPT_PATH.read_text(encoding="utf-8"),
        ],
    )

    if policy.get("mandatory_gate") != "PHASE37-END-TO-END-PORTAL-RUN-FLOW-GATE":
        errors.append("Phase 37 policy missing mandatory end-to-end flow gate")
    if policy.get("portal_flow_service") != str(SERVICE_PATH):
        errors.append("Phase 37 policy does not identify the portal flow service")
    if policy.get("arbitrary_command_execution_allowed") is not False:
        errors.append("Phase 37 policy allows arbitrary command execution")
    if set(policy.get("required_stage_statuses", [])) != REQUIRED_STAGE_STATUSES:
        errors.append("Phase 37 policy stage set does not match required stages")

    for artifact, name in [
        (policy, "policy"),
        (gate, "gate"),
        (audit, "audit"),
        (manifest, "manifest"),
    ]:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 37 {name} changed certification boundary")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 37 {name} claims official certification")
        if artifact.get("official_certification_granted") is not False:
            errors.append(f"Phase 37 {name} claims official certification grant")
        if artifact.get("production_readiness_claimed") is not False:
            errors.append(f"Phase 37 {name} claims production readiness")

    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
        "generation_success_claimed",
    ]:
        if policy.get(field) is not False:
            errors.append(f"Phase 37 policy has invalid safety field: {field}")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 37 policy does not keep ecosystem integrations mocked")
    if policy.get("local_readiness_scope") != "local_end_to_end_operator_portal_run_flow_only":
        errors.append("Phase 37 policy does not scope readiness to local flow only")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 37 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "Do not fake success",
        "do not fake generation success",
        "configured, unavailable, missing, passed, failed, and skipped",
        "certification_ready_not_certified",
        "mocked or simulated",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 37 prompt missing required phrase: {phrase}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in combined_source:
            errors.append(f"Phase 37 source includes forbidden term: {term}")


def validate_boundary_payload(payload: dict[str, Any], errors: list[str], context: str) -> None:
    boundaries = payload.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append(f"{context} does not expose safety boundaries")
        return
    safety = cast(dict[str, Any], boundaries)
    for key, expected in SAFETY_BOUNDARIES.items():
        if safety.get(key) != expected:
            errors.append(f"{context} changed safety boundary: {key}")


def validate_service_flow(errors: list[str]) -> None:
    report = EndToEndPortalRunFlowService().run(
        validation_command_ids=("phase34_runner_self_check",),
        collect_all=True,
        write_report=True,
    )
    if report.get("phase") != "phase37_end_to_end_portal_run_flow":
        errors.append("Phase 37 service returned an unexpected phase")
    if set(cast(dict[str, Any], report.get("stages", {}))) != REQUIRED_STAGE_STATUSES:
        errors.append("Phase 37 service did not expose all required stages")

    stages = cast(dict[str, dict[str, Any]], report.get("stages", {}))
    if stages.get("generation_command", {}).get("status") not in {"configured", "unavailable"}:
        errors.append("Phase 37 generation command status is not explicit")
    if stages.get("generation_command", {}).get("success_claimed") is not False:
        errors.append("Phase 37 faked generation success")
    if stages.get("export_bundle_ready", {}).get("status") != "passed":
        errors.append("Phase 37 export bundle did not become ready")
    if stages.get("validation_dry_run_ready", {}).get("status") != "passed":
        errors.append("Phase 37 validation dry-run did not become ready")
    if stages.get("validation_run", {}).get("status") not in {"passed", "failed"}:
        errors.append("Phase 37 validation run status is not passed/failed")
    if stages.get("evidence_dashboard_updated", {}).get("status") != "passed":
        errors.append("Phase 37 evidence dashboard did not observe validation report")
    if stages.get("download_available", {}).get("status") != "passed":
        errors.append("Phase 37 download did not become available")

    generation_status = cast(dict[str, Any], report.get("generation_status", {}))
    if generation_status.get("success_claimed") is not False:
        errors.append("Phase 37 generation status claimed success")
    if generation_status.get("generation_executed_by_phase37") is not False:
        errors.append("Phase 37 unexpectedly executed generation")
    validate_boundary_payload(report, errors, "Phase 37 service report")


def validate_run_script(errors: list[str]) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(RUN_SCRIPT_PATH),
            "--validation-command-id",
            "phase34_runner_self_check",
            "--no-write-report",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"Phase 37 run script failed: {result.stdout}{result.stderr}")
        return
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        errors.append("Phase 37 run script did not return a JSON object")
        return
    report = cast(dict[str, Any], payload)
    if report.get("generation_status", {}).get("success_claimed") is not False:
        errors.append("Phase 37 run script faked generation success")
    validate_boundary_payload(report, errors, "Phase 37 run script report")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 37 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    validate_service_flow(errors)
    validate_run_script(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 37 end-to-end portal run flow validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
