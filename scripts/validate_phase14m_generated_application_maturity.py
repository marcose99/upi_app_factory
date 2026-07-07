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

from scripts.build_generated_application_maturity_sweep import (
    EXPECTED_GENERATED_APP_TESTS,
    GENERATED_APP_ROOT,
    MATURITY_DIMENSIONS,
    READY,
    build_generated_application_maturity_sweep,
    validate_generated_application_maturity_sweep,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


POLICY_PATH = Path("policies/phase14m_generated_application_maturity_policy.json")
DOC_PATH = Path("docs/phase14m/generated_application_maturity_sweep.md")
SWEEP_PATH = Path("scripts/build_generated_application_maturity_sweep.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14m/generated_application_maturity_sweep_audit.json"
)
PHASE14L_PORTAL = Path("scripts/build_operator_portal_certification_dashboard_integration.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, SWEEP_PATH, AUDIT_PATH, PHASE14L_PORTAL]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "generated-application-maturity-sweep-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "GENERATED_APPLICATION_MATURITY_SWEEP":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    true_keys = [
        "primary_generated_application_must_be_real_local_app",
        "external_ecosystem_integrations_remain_mock",
        "maturity_sweep_only",
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

    for dimension in MATURITY_DIMENSIONS:
        if dimension not in policy.get("required_maturity_dimensions", []):
            failures.append(f"Policy missing maturity dimension: {dimension}")

    if not GENERATED_APP_ROOT.exists():
        failures.append(f"Generated application root missing: {GENERATED_APP_ROOT}")
    for test_path in EXPECTED_GENERATED_APP_TESTS:
        if not Path(test_path).exists():
            failures.append(f"Generated application test evidence missing: {test_path}")

    sweep = build_generated_application_maturity_sweep()
    if sweep.get("status") != READY:
        failures.append("Generated application maturity sweep should be ready")
    failures.extend(validate_generated_application_maturity_sweep(sweep))

    boundary_value = sweep.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Sweep must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Sweep missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(SWEEP_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Generated application maturity sweep CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Generated application maturity sweep CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "generated application maturity sweep",
        "real locally runnable application",
        "external ecosystem integrations remain mock or simulated",
        "does not overwrite the generated application",
        "generated application remains certification-ready, not certified",
        "final certification remains with authorized certifying authorities",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14M validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14M generated application maturity artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
