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

from scripts.build_governed_autonomy_control_plane import (
    BLOCKED_ACTIONS,
    DecisionStatus,
    LIFECYCLE_ACTIVITIES,
    READY,
    build_governed_autonomy_control_plane,
    decide_autonomy_action,
    validate_governed_autonomy_control_plane,
)


POLICY_PATH = Path("policies/phase13az_governed_autonomy_control_plane_policy.json")
DOC_PATH = Path("docs/phase13az/governed_a_to_z_autonomy_control_plane.md")
CONTROL_PLANE_PATH = Path("scripts/build_governed_autonomy_control_plane.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13az/governed_autonomy_control_plane_audit.json"
)
PHASE13AY_DASHBOARDS = Path("scripts/build_operator_portal_dashboard_panels.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, CONTROL_PLANE_PATH, AUDIT_PATH, PHASE13AY_DASHBOARDS]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-autonomy-control-plane-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "GOVERNED_A_TO_Z_AUTONOMY_CONTROL_PLANE_POLICY_ONLY":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13ay_operator_dashboards") is not True:
        failures.append("Policy must require Phase 13AY dashboards")
    if policy.get("control_plane_only") is not True:
        failures.append("Policy must be control-plane-only")
    if policy.get("maximum_default_autonomy_level") != 4:
        failures.append("Default autonomy level should be 4")

    for key in [
        "live_provider_calls_allowed_by_default",
        "external_system_calls_allowed_by_default",
        "arbitrary_shell_execution_allowed",
        "destructive_delete_allowed",
        "real_generated_application_overwrite_allowed_without_approval",
        "factory_self_modification_allowed_without_approval",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    for action in BLOCKED_ACTIONS:
        if action not in policy.get("blocked_actions", []):
            failures.append(f"Policy missing blocked action: {action}")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "arbitrary_shell_execution_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "real_worktree_mutated_by_control_plane",
        "application_generation_triggered_by_control_plane",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    control_plane = build_governed_autonomy_control_plane()
    if control_plane.get("status") != READY:
        failures.append("Control plane should be ready")
    failures.extend(validate_governed_autonomy_control_plane(control_plane))

    approved_read = decide_autonomy_action("VIEW_FACTORY_STATUS", 4)
    if approved_read.status != DecisionStatus.APPROVED:
        failures.append("Read-only status action should be approved")

    sandbox_generation = decide_autonomy_action("GENERATE_IN_SANDBOX", 4)
    if sandbox_generation.status != DecisionStatus.APPROVED:
        failures.append("Sandbox generation should be approved at level 4")

    promotion_without_approval = decide_autonomy_action(
        "PROMOTE_SANDBOX_TO_WORKTREE",
        4,
        sandbox_evidence_present=True,
    )
    if promotion_without_approval.status != DecisionStatus.HUMAN_APPROVAL_REQUIRED:
        failures.append("Worktree promotion without approval should require human approval")

    release_at_level_4 = decide_autonomy_action(
        "MERGE_MAIN",
        4,
        human_approved=True,
        sandbox_evidence_present=True,
    )
    if release_at_level_4.status != DecisionStatus.BLOCKED:
        failures.append("Release action should be blocked below level 5")

    prohibited = decide_autonomy_action("ARBITRARY_SHELL_COMMAND", 6, human_approved=True, sandbox_evidence_present=True)
    if prohibited.status != DecisionStatus.BLOCKED:
        failures.append("Arbitrary shell command must remain blocked")

    activity_values = control_plane.get("lifecycle_activities")
    if not isinstance(activity_values, list):
        failures.append("Lifecycle activities must be listed")
    else:
        activity_names = {str(activity) for activity in activity_values}
        for activity in LIFECYCLE_ACTIVITIES:
            if activity not in activity_names:
                failures.append(f"Missing lifecycle activity: {activity}")

    cli = subprocess.run(
        [sys.executable, str(CONTROL_PLANE_PATH), "--default-autonomy-level", "4"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Autonomy control plane CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Autonomy control plane CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed a-to-z autonomy control plane",
        "control-plane-only",
        "does not execute arbitrary shell commands",
        "does not delete the real generated application",
        "does not mutate the real worktree",
        "does not merge, tag, or release automatically",
        "autonomy levels",
        "covered lifecycle activities",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AZ validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 13AZ governed A-to-Z autonomy control plane artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
