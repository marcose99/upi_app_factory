#!/usr/bin/env python3
"""Validate Phase 13AF clean-slate regeneration safety artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.guard_clean_slate_regeneration import (  # noqa: E402
    DEFAULT_GENERATED_APPLICATION,
    SafetyDecision,
    build_clean_slate_safety_plan,
    validate_plans,
)


POLICY_PATH = Path("policies/phase13af_clean_slate_regeneration_safety_policy.json")
DOC_PATH = Path("docs/phase13af/clean_slate_regeneration_safety_boundary.md")
GUARD_PATH = Path("scripts/guard_clean_slate_regeneration.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13af/clean_slate_regeneration_safety_audit.json"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, GUARD_PATH, AUDIT_PATH]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "clean-slate-regeneration-safety-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_DRY_RUN_DELETE_GUARD":
        failures.append("Policy mode must be LOCAL_ONLY_DRY_RUN_DELETE_GUARD")

    if policy.get("destructive_delete_allowed_in_this_phase") is not False:
        failures.append("Phase 13AF must not allow destructive delete")

    if policy.get("human_approval_required_before_delete") is not True:
        failures.append("Delete must require human approval")

    if policy.get("backup_required_before_delete") is not True:
        failures.append("Backup must be required before delete")

    allowed_targets = set(policy.get("allowed_delete_targets", []))
    if str(DEFAULT_GENERATED_APPLICATION) not in allowed_targets:
        failures.append("Policy must allow only the generated_application target")

    blocked_targets = set(policy.get("blocked_delete_targets", []))
    for blocked in [".git", "docs", "policies", "scripts", "tests"]:
        if blocked not in blocked_targets:
            failures.append(f"Policy missing blocked target: {blocked}")

    if audit.get("schema_version") != "clean-slate-regeneration-safety-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("destructive_delete_performed") is not False:
        failures.append("Audit must confirm no destructive delete was performed")

    plan = build_clean_slate_safety_plan(Path.cwd())
    if plan.decision != SafetyDecision.ALLOW_DRY_RUN_PLAN.value:
        failures.append("Default generated_application dry-run plan should be allowed")

    blocked_plan = build_clean_slate_safety_plan(Path.cwd(), Path("docs"))
    if blocked_plan.decision != SafetyDecision.BLOCK.value:
        failures.append("Docs path must be blocked")

    plan_failures = validate_plans([plan, blocked_plan])
    if plan_failures:
        failures.extend(plan_failures)

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "clean-slate regeneration safety boundary",
        "non-destructive",
        "allowed delete target",
        "blocked delete targets",
        "human approval",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    cli = subprocess.run(
        [
            sys.executable,
            str(GUARD_PATH),
            "--project-root",
            str(Path.cwd()),
            "--target",
            str(DEFAULT_GENERATED_APPLICATION),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Guard CLI should allow default generated_application dry-run plan")
    elif "ALLOW_DRY_RUN_PLAN" not in cli.stdout:
        failures.append("Guard CLI did not emit ALLOW_DRY_RUN_PLAN")

    blocked_cli = subprocess.run(
        [
            sys.executable,
            str(GUARD_PATH),
            "--project-root",
            str(Path.cwd()),
            "--target",
            "docs",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Guard CLI should block docs target with exit code 2")
    elif "BLOCK" not in blocked_cli.stdout:
        failures.append("Guard CLI did not emit BLOCK for docs target")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AF validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AF clean-slate regeneration safety artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
