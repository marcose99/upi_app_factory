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
from scripts.build_operator_portal_certification_dashboard_integration import (
    OPERATOR_VISIBLE_WORDING,
    PORTAL_CARDS,
    READY,
    RECOMMENDED_ROUTES,
    build_operator_portal_certification_dashboard_integration,
    validate_operator_portal_certification_dashboard_integration,
)


POLICY_PATH = Path("policies/phase14l_operator_portal_certification_dashboard_policy.json")
DOC_PATH = Path("docs/phase14l/operator_portal_certification_dashboard_integration.md")
INTEGRATION_PATH = Path("scripts/build_operator_portal_certification_dashboard_integration.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14l/operator_portal_certification_dashboard_audit.json"
)
PHASE14K_LOOP = Path("scripts/run_governed_autonomous_phase_execution_loop.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, INTEGRATION_PATH, AUDIT_PATH, PHASE14K_LOOP]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "operator-portal-certification-dashboard-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "OPERATOR_PORTAL_CERTIFICATION_READINESS_DASHBOARD_INTEGRATION":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    true_keys = [
        "portal_integration_contract_only",
        "operator_visible_status_must_be_not_certified",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]
    for key in true_keys:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

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
            failures.append(f"Audit must keep {key} false")

    for card_id in PORTAL_CARDS:
        if card_id not in policy.get("required_portal_cards", []):
            failures.append(f"Policy missing portal card: {card_id}")
    for route in RECOMMENDED_ROUTES:
        if route not in policy.get("recommended_routes", []):
            failures.append(f"Policy missing route: {route}")

    integration = build_operator_portal_certification_dashboard_integration()
    if integration.get("status") != READY:
        failures.append("Operator portal certification dashboard integration should be ready")
    failures.extend(validate_operator_portal_certification_dashboard_integration(integration))

    wording_value = integration.get("operator_visible_wording")
    if not isinstance(wording_value, list):
        failures.append("Integration must list operator wording")
    else:
        wording_names = {str(item) for item in wording_value}
        for phrase in OPERATOR_VISIBLE_WORDING:
            if phrase not in wording_names:
                failures.append(f"Integration missing wording: {phrase}")

    boundary_value = integration.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Integration must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Integration missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(INTEGRATION_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Operator portal certification dashboard integration CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Operator portal certification dashboard integration CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "operator portal certification readiness dashboard integration",
        "certification-ready, not certified",
        "the factory does not self-certify generated applications",
        "final certification remains with authorized certifying authorities",
        "phase 14l does not claim official certification",
        "phase 14l does not execute a release",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14L validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14L operator portal certification dashboard artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
