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

from scripts.build_governed_autonomous_self_engineering_orchestrator import (
    ALLOWED_AUTONOMOUS_ACTIONS,
    BLOCKED_ACTIONS,
    ORCHESTRATION_STEPS,
    READY,
    build_governed_autonomous_self_engineering_orchestrator,
    validate_governed_autonomous_self_engineering_orchestrator,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


POLICY_PATH = Path("policies/phase14j_governed_autonomous_self_engineering_policy.json")
DOC_PATH = Path("docs/phase14j/governed_autonomous_self_engineering_orchestrator.md")
ORCHESTRATOR_PATH = Path("scripts/build_governed_autonomous_self_engineering_orchestrator.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14j/governed_autonomous_self_engineering_orchestrator_audit.json"
)
PHASE14I_DASHBOARD = Path("scripts/build_certification_readiness_dashboard_index.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, ORCHESTRATOR_PATH, AUDIT_PATH, PHASE14I_DASHBOARD]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-autonomous-self-engineering-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "GOVERNED_AUTONOMOUS_SELF_ENGINEERING_ORCHESTRATOR":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    true_keys = [
        "governed_autonomous_self_engineering_allowed",
        "governed_low_risk_self_healing_allowed",
        "governed_self_evolution_allowed",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
    ]
    for key in true_keys:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    false_keys = [
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
    for key in false_keys:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    audit_false_keys = [
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
    for key in audit_false_keys:
        if audit.get(key) is not False:
            failures.append(f"Audit must keep {key} false")

    for action in ALLOWED_AUTONOMOUS_ACTIONS:
        if action not in policy.get("allowed_autonomous_actions", []):
            failures.append(f"Policy missing allowed autonomous action: {action}")
    for action in BLOCKED_ACTIONS:
        if action not in policy.get("blocked_actions", []):
            failures.append(f"Policy missing blocked action: {action}")

    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    if orchestrator.get("status") != READY:
        failures.append("Governed autonomous self-engineering orchestrator should be ready")
    failures.extend(validate_governed_autonomous_self_engineering_orchestrator(orchestrator))

    steps_value = orchestrator.get("orchestration_steps")
    if not isinstance(steps_value, list):
        failures.append("Orchestrator must list orchestration steps")
    else:
        step_ids: set[str] = set()
        for step in steps_value:
            if isinstance(step, dict):
                step_id = step.get("step_id")
                if isinstance(step_id, str):
                    step_ids.add(step_id)
        for step_id in ORCHESTRATION_STEPS:
            if step_id not in step_ids:
                failures.append(f"Orchestrator missing step: {step_id}")

    boundary_value = orchestrator.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Orchestrator must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Orchestrator missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(ORCHESTRATOR_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Governed autonomous self-engineering orchestrator CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Governed autonomous self-engineering orchestrator CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed autonomous self-engineering orchestrator",
        "not uncontrolled autonomy",
        "human approval remains required",
        "generated application is certification-ready, not certified",
        "the factory does not self-certify generated applications",
        "the factory does not grant official certification",
        "final certification remains with authorized certifying authorities",
        "stop_at_human_approval_gate",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14J validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14J governed autonomous self-engineering artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
