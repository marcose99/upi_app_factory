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

from scripts.run_sandbox_autonomous_generation_validation_loop import (
    READY,
    build_sandbox_loop_report,
    validate_sandbox_loop_report,
)


POLICY_PATH = Path("policies/phase14b_sandbox_autonomous_generation_validation_policy.json")
DOC_PATH = Path("docs/phase14b/sandbox_autonomous_generation_validation_loop.md")
LOOP_PATH = Path("scripts/run_sandbox_autonomous_generation_validation_loop.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14b/sandbox_autonomous_generation_validation_audit.json"
)
PHASE13AZ_CONTROL_PLANE = Path("scripts/build_governed_autonomy_control_plane.py")
PHASE14A_EXECUTOR = Path("scripts/build_autonomous_lifecycle_plan_executor.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, LOOP_PATH, AUDIT_PATH, PHASE13AZ_CONTROL_PLANE, PHASE14A_EXECUTOR]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "sandbox-autonomous-generation-validation-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "SANDBOX_ONLY_AUTONOMOUS_GENERATION_AND_VALIDATION":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13az_autonomy_control_plane") is not True:
        failures.append("Policy must require Phase 13AZ")
    if policy.get("requires_phase14a_lifecycle_plan_executor") is not True:
        failures.append("Policy must require Phase 14A")
    if policy.get("sandbox_only") is not True:
        failures.append("Policy must mark sandbox_only true")

    for key in [
        "real_generated_application_write_allowed",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed",
        "real_worktree_mutation_allowed",
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
        "real_generated_application_written",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "real_worktree_mutated",
        "arbitrary_shell_execution_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    report = build_sandbox_loop_report()
    if report.get("status") != READY:
        failures.append("Sandbox loop report should be ready")
    failures.extend(validate_sandbox_loop_report(report))

    cli = subprocess.run(
        [sys.executable, str(LOOP_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Sandbox loop CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Sandbox loop CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "sandbox autonomous generation and validation loop",
        "sandbox-only",
        "does not mutate the real generated application",
        "does not promote sandbox output to the real worktree",
        "does not execute arbitrary shell commands",
        "does not merge, tag, or release automatically",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14B validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14B sandbox autonomous generation and validation loop artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
