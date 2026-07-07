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
from scripts.run_governed_autonomous_phase_execution_loop import (
    CANDIDATE_NEXT_PHASES,
    EXECUTION_LOOP_STAGES,
    HUMAN_GATED_ACTIONS,
    READY,
    VALIDATION_GATES,
    build_governed_autonomous_phase_execution_loop,
    validate_governed_autonomous_phase_execution_loop,
)


POLICY_PATH = Path("policies/phase14k_governed_autonomous_phase_execution_policy.json")
DOC_PATH = Path("docs/phase14k/governed_autonomous_phase_execution_loop.md")
LOOP_PATH = Path("scripts/run_governed_autonomous_phase_execution_loop.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14k/governed_autonomous_phase_execution_audit.json"
)
PHASE14J_ORCHESTRATOR = Path("scripts/build_governed_autonomous_self_engineering_orchestrator.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, LOOP_PATH, AUDIT_PATH, PHASE14J_ORCHESTRATOR]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-autonomous-phase-execution-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "GOVERNED_AUTONOMOUS_PHASE_EXECUTION_LOOP":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    true_keys = [
        "autonomous_execution_allowed_inside_governed_branch",
        "low_risk_self_healing_allowed",
        "self_evolution_allowed_for_docs_policies_tests_evidence",
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

    for stage_id in EXECUTION_LOOP_STAGES:
        if stage_id not in policy.get("execution_loop_stages", []):
            failures.append(f"Policy missing execution loop stage: {stage_id}")
    for candidate in CANDIDATE_NEXT_PHASES:
        if candidate not in policy.get("candidate_next_phases", []):
            failures.append(f"Policy missing candidate phase: {candidate}")

    loop = build_governed_autonomous_phase_execution_loop()
    if loop.get("status") != READY:
        failures.append("Governed autonomous phase execution loop should be ready")
    failures.extend(validate_governed_autonomous_phase_execution_loop(loop))

    gates_value = loop.get("validation_gates")
    if not isinstance(gates_value, list):
        failures.append("Loop validation_gates must be a list")
    else:
        gate_names = {str(item) for item in gates_value}
        for gate in VALIDATION_GATES:
            if gate not in gate_names:
                failures.append(f"Loop missing validation gate: {gate}")

    actions_value = loop.get("human_gated_actions")
    if not isinstance(actions_value, list):
        failures.append("Loop human_gated_actions must be a list")
    else:
        action_names = {str(item) for item in actions_value}
        for action in HUMAN_GATED_ACTIONS:
            if action not in action_names:
                failures.append(f"Loop missing human-gated action: {action}")

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
        failures.append("Governed autonomous phase execution loop CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Governed autonomous phase execution loop CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed autonomous phase execution loop",
        "phase 14j orchestrator",
        "apply only policy-approved low-risk repairs",
        "stop at human approval",
        "generated application is certification-ready, not certified",
        "the factory does not self-certify generated applications",
        "final certification remains with authorized certifying authorities",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14K validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14K governed autonomous phase execution loop artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
