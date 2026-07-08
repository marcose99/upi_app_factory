#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.evidence_dashboard import build_dashboard_summary  # noqa: E402
from factory.operator_portal.validation_runner import (  # noqa: E402
    DEFAULT_COMMAND_IDS,
    CommandNotAllowedError,
    ValidationRunnerService,
)


APP_ID = "upi_dispute_resolution"
SERVICE_PATH = Path("factory/operator_portal/validation_runner.py")
RUN_SCRIPT_PATH = Path("scripts/run_phase34_operator_portal_validation_runner.py")
POLICY_PATH = Path("policies/phase34_operator_portal_validation_runner_policy.json")
PROMPT_PATH = Path("prompts/phase34/operator_portal_validation_runner_prompt.md")
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase34"
)
RUN_REPORT_PATH = ARTIFACT_DIR / "operator_portal_validation_run_report.json"

REQUIRED_FILES = [
    SERVICE_PATH,
    RUN_SCRIPT_PATH,
    POLICY_PATH,
    PROMPT_PATH,
    ARTIFACT_DIR / "operator_portal_validation_runner_gate.json",
    ARTIFACT_DIR / "operator_portal_validation_runner_audit.json",
    ARTIFACT_DIR / "operator_portal_validation_runner_manifest.json",
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
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(POLICY_PATH)
    gate = load_json(ARTIFACT_DIR / "operator_portal_validation_runner_gate.json")
    audit = load_json(ARTIFACT_DIR / "operator_portal_validation_runner_audit.json")
    manifest = load_json(ARTIFACT_DIR / "operator_portal_validation_runner_manifest.json")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    service_source = SERVICE_PATH.read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE34-OPERATOR-PORTAL-VALIDATION-RUNNER-GATE":
        errors.append("Phase 34 policy missing mandatory validation runner gate")
    if policy.get("validation_runner_service") != str(SERVICE_PATH):
        errors.append("Phase 34 policy does not identify the validation runner service")
    if policy.get("arbitrary_command_execution_allowed") is not False:
        errors.append("Phase 34 policy allows arbitrary command execution")

    for artifact, name in [
        (policy, "policy"),
        (gate, "gate"),
        (audit, "audit"),
        (manifest, "manifest"),
    ]:
        if artifact.get("certification_boundary") != "certification_ready_not_certified":
            errors.append(f"Phase 34 {name} changed certification boundary")
        if artifact.get("official_certification_claimed") is not False:
            errors.append(f"Phase 34 {name} claims official certification")
        if artifact.get("production_readiness_claimed") is not False:
            errors.append(f"Phase 34 {name} claims production readiness")

    for field in [
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
    ]:
        if policy.get(field) is not False:
            errors.append(f"Phase 34 policy has invalid safety field: {field}")
    if policy.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append("Phase 34 policy does not keep ecosystem integrations mocked")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        if contract_path not in prompt:
            errors.append(f"Phase 34 prompt does not inherit contract: {contract_path}")
    for phrase in [
        "allowlist",
        "dry-run",
        "certification_ready_not_certified",
        "must not fake validation success",
        "must never execute arbitrary command strings",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 34 prompt missing required phrase: {phrase}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in service_source:
            errors.append(f"Validation runner source includes forbidden term: {term}")


def validate_dry_run(errors: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(RUN_SCRIPT_PATH), "--dry-run"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"Phase 34 dry-run script failed: {result.stdout}{result.stderr}")
        return
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        errors.append("Phase 34 dry-run script did not return a JSON object")
        return
    report = cast(dict[str, Any], payload)
    if report.get("dry_run") is not True:
        errors.append("Phase 34 dry-run did not report dry_run=true")
    command_results = report.get("command_results")
    if not isinstance(command_results, list) or not command_results:
        errors.append("Phase 34 dry-run did not list approved commands")
        return
    returned_ids = {entry.get("command_id") for entry in command_results if isinstance(entry, dict)}
    if set(DEFAULT_COMMAND_IDS) != returned_ids:
        errors.append("Phase 34 dry-run command list does not match the approved default set")
    for entry in command_results:
        if isinstance(entry, dict) and "return_code" in entry:
            errors.append("Phase 34 dry-run executed a command instead of listing it")


def validate_runner_execution(errors: list[str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmpdir:
        report_path = Path(tmpdir) / "phase34_self_check_report.json"
        service = ValidationRunnerService(report_path=report_path)
        report = service.run(
            command_ids=("phase34_runner_self_check",),
            collect_all=True,
            write_report=True,
        )
        if not report_path.is_file():
            errors.append("Phase 34 runner did not write a structured run report")
        reloaded = load_json(report_path)

    if report.get("status") != "passed":
        errors.append("Phase 34 safe self-check did not pass")
    command_results = report.get("command_results")
    if not isinstance(command_results, list) or not command_results:
        errors.append("Phase 34 run report does not contain command statuses")
        return report
    first = cast(dict[str, Any], command_results[0])
    if first.get("status") != "passed":
        errors.append("Phase 34 command result does not contain passed status")
    if first.get("return_code") != 0:
        errors.append("Phase 34 command result does not contain return_code=0")
    if "duration_seconds" not in first:
        errors.append("Phase 34 command result does not contain duration")
    if reloaded.get("command_results") != report.get("command_results"):
        errors.append("Phase 34 persisted run report does not match returned report")

    service = ValidationRunnerService()
    try:
        service.reject_unapproved_command("python -c arbitrary shell text")
    except CommandNotAllowedError:
        pass
    else:
        errors.append("Phase 34 runner accepted an unapproved arbitrary command")

    return report


def validate_boundaries(report: dict[str, Any], errors: list[str]) -> None:
    boundaries = report.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append("Phase 34 report does not expose safety boundaries")
        return
    safety = cast(dict[str, Any], boundaries)
    if safety.get("certification_boundary") != "certification_ready_not_certified":
        errors.append("Phase 34 report does not preserve certification-ready-not-certified")
    for field in [
        "official_certification_claimed",
        "official_certification_granted",
        "production_readiness_claimed",
        "live_provider_calls_allowed",
        "real_secrets_allowed",
        "deployment_allowed",
        "merge_allowed",
        "tag_allowed",
        "push_allowed",
        "arbitrary_shell_text_allowed",
        "shell_true_used",
    ]:
        if safety.get(field) is not False:
            errors.append(f"Phase 34 report has invalid safety boundary: {field}")


def validate_dashboard_truthfulness(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        missing_summary = build_dashboard_summary(project_root=Path(tmpdir))
    missing_status = cast(
        dict[str, Any],
        missing_summary.get("phase34_validation_runner_report_status", {}),
    )
    if missing_status.get("status") != "missing":
        errors.append("Dashboard faked Phase 34 run report availability")

    available_summary = build_dashboard_summary()
    available_status = cast(
        dict[str, Any],
        available_summary.get("phase34_validation_runner_report_status", {}),
    )
    if available_status.get("run_report_status") not in {"available", "missing"}:
        errors.append("Dashboard Phase 34 run report status is not explicit")


def validate() -> list[str]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return [f"Missing Phase 34 artifacts: {missing}"]

    errors: list[str] = []
    validate_static_artifacts(errors)
    validate_dry_run(errors)
    report = validate_runner_execution(errors)
    validate_boundaries(report, errors)
    validate_dashboard_truthfulness(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(json.dumps({"errors": errors, "passed": False}, indent=2, sort_keys=True))
        return 1
    print("Phase 34 operator portal governed validation runner validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
