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

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_runtime_dashboard_proof import (
    OPERATOR_VISIBLE_WORDING,
    READY,
    RUNTIME_ROUTES,
    build_operator_portal_runtime_dashboard_proof,
    validate_operator_portal_runtime_dashboard_proof,
)


POLICY_PATH = Path("policies/phase14p_operator_portal_runtime_dashboard_policy.json")
DOC_PATH = Path("docs/phase14p/operator_portal_runtime_dashboard_proof.md")
PROOF_PATH = Path("scripts/build_operator_portal_runtime_dashboard_proof.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14p/operator_portal_runtime_dashboard_audit.json"
)
PHASE14O_PROOF = Path("scripts/build_actual_clean_checkout_v1_replay_proof.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, PROOF_PATH, AUDIT_PATH, PHASE14O_PROOF]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "operator-portal-runtime-dashboard-proof-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "OPERATOR_PORTAL_RUNTIME_DASHBOARD_PROOF":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    true_policy_keys = [
        "portal_runtime_probe_required",
        "operator_visible_status_must_be_not_certified",
        "external_ecosystem_integrations_remain_mock",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_release_candidate_declaration",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]
    for key in true_policy_keys:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")

    true_audit_keys = [
        "portal_runtime_probe_performed",
        "operator_visible_status_must_be_not_certified",
        "external_ecosystem_integrations_remain_mock",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_release_candidate_declaration",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]
    for key in true_audit_keys:
        if audit.get(key) is not True:
            failures.append(f"Executed audit must keep {key} true")

    false_policy_keys = [
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_allowed",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed_without_approval",
        "arbitrary_shell_execution_allowed",
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "factory_self_modification_without_policy_allowed",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]
    for key in false_policy_keys:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    false_audit_keys = [
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "arbitrary_shell_execution_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "factory_self_modification_without_policy_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]
    for key in false_audit_keys:
        if audit.get(key) is not False:
            failures.append(f"Executed audit must keep {key} false")

    for route in RUNTIME_ROUTES:
        if route not in policy.get("required_runtime_routes", []):
            failures.append(f"Policy missing runtime route: {route}")
    for phrase in OPERATOR_VISIBLE_WORDING:
        if phrase not in policy.get("required_operator_wording", []):
            failures.append(f"Policy missing operator wording: {phrase}")

    proof_plan = build_operator_portal_runtime_dashboard_proof(execute_probe=False)
    if proof_plan.get("status") != READY:
        failures.append("Operator portal runtime dashboard proof plan should be ready")
    failures.extend(validate_operator_portal_runtime_dashboard_proof(proof_plan))

    if audit.get("status") != READY:
        failures.append("Executed runtime audit should be ready")
    failures.extend(validate_operator_portal_runtime_dashboard_proof(audit, require_executed=True))

    boundary_value = audit.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Executed audit must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Executed audit missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(PROOF_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Operator portal runtime dashboard proof CLI plan should pass")
    elif READY not in cli.stdout:
        failures.append("Operator portal runtime dashboard proof CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "operator portal runtime dashboard proof",
        "actual local http route/api probes",
        "certification-ready, not certified",
        "external ecosystem integrations remain mock or simulated",
        "factory does not self-certify",
        "final certification remains with authorized certifying authorities",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14P validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14P operator portal runtime dashboard proof artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
