#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_authority_findings_remediation_loop import (
    FINDING_SEVERITIES,
    FINDING_STATUSES,
    READY,
    REQUIRED_REGISTERS,
    build_authority_findings_remediation_loop,
    validate_authority_findings_remediation_loop,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


POLICY_PATH = Path("policies/phase14g_authority_findings_remediation_policy.json")
DOC_PATH = Path("docs/phase14g/authority_findings_remediation_loop.md")
LOOP_PATH = Path("scripts/build_authority_findings_remediation_loop.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14g/authority_findings_remediation_audit.json"
)
PHASE14F_WORKSPACE = Path("scripts/build_certifying_authority_review_workspace.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, LOOP_PATH, AUDIT_PATH, PHASE14F_WORKSPACE]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "authority-findings-remediation-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "AUTHORITY_FINDINGS_REGISTER_AND_REMEDIATION_LOOP":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "remediation_loop_only",
    ]:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    for key in [
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "automatic_remediation_execution_allowed",
        "release_execution_allowed",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed_without_approval",
        "arbitrary_shell_execution_allowed",
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "factory_self_modification_allowed",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    for key in [
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "automatic_remediation_execution_performed",
        "release_execution_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "arbitrary_shell_execution_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must keep {key} false")

    for severity in FINDING_SEVERITIES:
        if severity not in policy.get("allowed_finding_severities", []):
            failures.append(f"Policy missing severity: {severity}")
    for status in FINDING_STATUSES:
        if status not in policy.get("required_finding_statuses", []):
            failures.append(f"Policy missing finding status: {status}")
    for register in REQUIRED_REGISTERS:
        if register not in policy.get("required_registers", []):
            failures.append(f"Policy missing register: {register}")

    loop = build_authority_findings_remediation_loop()
    if loop.get("status") != READY:
        failures.append("Authority findings remediation loop should be ready")
    failures.extend(validate_authority_findings_remediation_loop(loop))

    boundary_value = loop.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Loop must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Loop missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(LOOP_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Authority findings remediation loop CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Authority findings remediation loop CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "authority findings register and remediation loop",
        "generated application remains certification-ready, not certified",
        "the factory does not self-certify generated applications",
        "the factory does not grant official certification",
        "final certification remains with authorized certifying authorities",
        "does not automatically execute remediation",
        "does not execute a release",
        "official certification decision",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14G validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14G authority findings remediation loop artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
