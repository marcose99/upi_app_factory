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

from scripts.build_autonomous_lifecycle_plan_executor import (
    READY,
    REQUIRED_STEP_IDS,
    build_autonomous_lifecycle_plan,
    validate_autonomous_lifecycle_plan,
)


POLICY_PATH = Path("policies/phase14a_autonomous_lifecycle_plan_executor_policy.json")
DOC_PATH = Path("docs/phase14a/autonomous_lifecycle_plan_executor.md")
EXECUTOR_PATH = Path("scripts/build_autonomous_lifecycle_plan_executor.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14a/autonomous_lifecycle_plan_executor_audit.json"
)
PHASE13AZ_CONTROL_PLANE = Path("scripts/build_governed_autonomy_control_plane.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, EXECUTOR_PATH, AUDIT_PATH, PHASE13AZ_CONTROL_PLANE]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "autonomous-lifecycle-plan-executor-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "PLAN_ONLY_AUTONOMOUS_LIFECYCLE_EXECUTOR":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13az_autonomy_control_plane") is not True:
        failures.append("Policy must require Phase 13AZ control plane")
    if policy.get("plan_only") is not True:
        failures.append("Policy must keep plan_only true")

    for key in [
        "real_command_execution_allowed",
        "worktree_mutation_allowed",
        "release_action_allowed",
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "arbitrary_shell_execution_allowed",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed",
        "factory_self_modification_allowed",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("required_lifecycle_steps", [])) != set(REQUIRED_STEP_IDS):
        failures.append("Policy lifecycle steps do not match executor")

    for key in [
        "real_command_execution_performed",
        "real_worktree_mutated",
        "release_action_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "arbitrary_shell_execution_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    plan = build_autonomous_lifecycle_plan()
    if plan.get("status") != READY:
        failures.append("Lifecycle plan should be ready")
    failures.extend(validate_autonomous_lifecycle_plan(plan))

    steps = plan.get("steps")
    if not isinstance(steps, list):
        failures.append("Lifecycle plan steps must be listed")
    else:
        for step in steps:
            if not isinstance(step, dict):
                failures.append("Lifecycle step must be an object")
                continue
            if step.get("execution_enabled") is not False:
                failures.append("Lifecycle steps must not execute in Phase 14A")
            decision = step.get("decision")
            if not isinstance(decision, dict):
                failures.append("Lifecycle step must include control-plane decision")

    cli = subprocess.run(
        [sys.executable, str(EXECUTOR_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Lifecycle plan executor CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Lifecycle plan executor CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "autonomous lifecycle plan executor",
        "plan-only",
        "does not execute shell commands",
        "does not mutate the real worktree",
        "does not delete the real generated application",
        "does not merge, tag, or release automatically",
        "required lifecycle plan steps",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14A validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14A autonomous lifecycle plan executor artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
