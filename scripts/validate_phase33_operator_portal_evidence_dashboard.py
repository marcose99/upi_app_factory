#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from factory.operator_portal.evidence_dashboard import build_dashboard_summary


APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = Path("factory/operator_portal/evidence_dashboard.py")
SCRIPT_PATH = Path("scripts/show_phase33_operator_portal_evidence_dashboard.py")
POLICY_PATH = Path("policies/phase33_operator_portal_evidence_dashboard_policy.json")
PROMPT_PATH = Path("prompts/phase33/operator_portal_evidence_dashboard_prompt.md")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase33"
)

REQUIRED_FILES = [
    SERVICE_PATH,
    SCRIPT_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    ARTIFACT_DIR / "operator_portal_evidence_dashboard_gate.json",
    ARTIFACT_DIR / "operator_portal_evidence_dashboard_audit.json",
    ARTIFACT_DIR / "operator_portal_evidence_dashboard_manifest.json",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "operator_portal_evidence_dashboard_gate.json")
    audit = load_json(ARTIFACT_DIR / "operator_portal_evidence_dashboard_audit.json")
    manifest = load_json(ARTIFACT_DIR / "operator_portal_evidence_dashboard_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE33-OPERATOR-PORTAL-EVIDENCE-DASHBOARD-GATE":
        errors.append("Phase 33 policy missing mandatory evidence dashboard gate")
    if policy.get("dashboard_service") != str(SERVICE_PATH):
        errors.append("Phase 33 policy does not identify the evidence dashboard service")
    if policy.get("dashboard_must_not_fake_success") is not True:
        errors.append("Phase 33 policy does not prohibit fake evidence success")

    for artifact, name in [
        (policy, "policy"),
        (gate, "gate"),
        (audit, "audit"),
        (manifest, "manifest"),
    ]:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 33 {name} changed certification boundary")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 33 {name} claims official certification")
        if artifact.get("production_readiness_claimed") is not False:
            errors.append(f"Phase 33 {name} claims production readiness")

    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
    ]:
        if policy.get(field) is not False:
            errors.append(f"Phase 33 policy has invalid safety field: {field}")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 33 policy does not keep ecosystem integrations mocked")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 33 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "Phase 28",
        "Phase 29",
        "Phase 30",
        "Phase 31",
        "Phase 32",
        "certification_ready_not_certified",
        "mocked or simulated",
        "must not fake success",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 33 prompt missing required phrase: {phrase}")


def run_dashboard_script(errors: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"Phase 33 dashboard script failed: {result.stdout}{result.stderr}")
        return {}
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        errors.append("Phase 33 dashboard script did not return a JSON object")
        return {}
    return cast(dict[str, Any], value)


def validate_dashboard_payload(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("app_id") != APP_ID:
        errors.append("Dashboard does not expose the current app id")

    coverage = payload.get("phase_coverage")
    if not isinstance(coverage, dict):
        errors.append("Dashboard does not expose phase coverage")
        coverage = {}
    covered_phases = set(cast(dict[str, Any], coverage).get("covered_phases", []))
    for phase in ["phase28", "phase29", "phase30", "phase31", "phase32"]:
        if phase not in covered_phases:
            errors.append(f"Dashboard phase coverage missing {phase}")

    artifacts = payload.get("lifecycle_artifact_availability")
    if not isinstance(artifacts, dict):
        errors.append("Dashboard does not expose lifecycle artifact availability")
        artifacts = {}
    for phase in ["phase28", "phase29", "phase30", "phase31", "phase32"]:
        if phase not in artifacts:
            errors.append(f"Dashboard evidence visibility missing {phase}")

    if not payload.get("validator_commands"):
        errors.append("Dashboard does not expose validator command list")
    if not payload.get("test_commands"):
        errors.append("Dashboard does not expose test command list")

    bundle_metadata = payload.get("phase31_export_bundle_metadata")
    if not isinstance(bundle_metadata, dict):
        errors.append("Dashboard does not expose Phase 31 bundle metadata")
        bundle_metadata = {}
    if cast(dict[str, Any], bundle_metadata).get("status") not in {
        "available",
        "partial",
        "missing",
    }:
        errors.append("Dashboard Phase 31 bundle metadata status is not explicit")

    phase32_status = payload.get("phase32_download_center_service_status")
    if not isinstance(phase32_status, dict):
        errors.append("Dashboard does not expose Phase 32 download-center status")

    boundaries = payload.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append("Dashboard does not expose safety boundaries")
        boundaries = {}
    boundary = cast(dict[str, Any], boundaries)
    expected_false_fields = [
        "official_certification_claimed",
        "official_certification_granted",
        "production_readiness_claimed",
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
    ]
    if boundary.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Dashboard does not preserve certification_ready_not_certified")
    for field in expected_false_fields:
        if boundary.get(field) is not False:
            errors.append(f"Dashboard safety boundary is invalid: {field}")
    if boundary.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Dashboard does not preserve mocked/simulated ecosystem boundary")
    if boundary.get("mocked_simulated_ecosystem_boundary") is not True:
        errors.append("Dashboard does not expose mocked/simulated ecosystem boundary")


def validate_missing_evidence_is_not_faked(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = build_dashboard_summary(project_root=Path(tmpdir))
    artifacts = summary.get("lifecycle_artifact_availability", {})
    if not isinstance(artifacts, dict):
        errors.append("Missing evidence dashboard did not expose artifact statuses")
        return
    for phase in ["phase28", "phase29", "phase30", "phase31", "phase32"]:
        phase_status = cast(dict[str, Any], artifacts.get(phase, {}))
        if phase_status.get("status") != "missing":
            errors.append(f"Dashboard faked evidence success for absent {phase}")
    bundle_metadata = cast(dict[str, Any], summary.get("phase31_export_bundle_metadata", {}))
    if bundle_metadata.get("status") != "missing":
        errors.append("Dashboard faked Phase 31 bundle success when bundle was absent")
    success_claim = cast(dict[str, Any], summary.get("dashboard_success_claim", {}))
    if success_claim.get("status") != "not_claimed":
        errors.append("Dashboard claimed success with absent evidence")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 33 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    payload = build_dashboard_summary()
    validate_dashboard_payload(payload, errors)
    script_payload = run_dashboard_script(errors)
    if script_payload:
        validate_dashboard_payload(script_payload, errors)
    validate_missing_evidence_is_not_faked(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 33 operator portal evidence dashboard validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
