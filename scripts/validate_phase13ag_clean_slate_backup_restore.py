#!/usr/bin/env python3
"""Validate Phase 13AG clean-slate backup/restore artifacts."""

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

from scripts.build_clean_slate_backup_restore_plan import (  # noqa: E402
    DEFAULT_SOURCE,
    build_backup_restore_plan,
    validate_backup_restore_plan,
)


POLICY_PATH = Path("policies/phase13ag_clean_slate_backup_restore_policy.json")
DOC_PATH = Path("docs/phase13ag/clean_slate_backup_restore_evidence_preservation.md")
PLANNER_PATH = Path("scripts/build_clean_slate_backup_restore_plan.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ag/clean_slate_backup_restore_audit.json"
)
PHASE13AF_GUARD = Path("scripts/guard_clean_slate_regeneration.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, PLANNER_PATH, AUDIT_PATH, PHASE13AF_GUARD]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "clean-slate-backup-restore-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_NON_DESTRUCTIVE_BACKUP_RESTORE_PLAN":
        failures.append("Policy mode mismatch")

    if policy.get("requires_phase13af_guard") is not True:
        failures.append("Policy must require Phase 13AF guard")

    if policy.get("destructive_delete_allowed_in_this_phase") is not False:
        failures.append("Phase 13AG must not allow destructive delete")

    if policy.get("backup_required_before_delete") is not True:
        failures.append("Backup must be required before delete")

    if policy.get("restore_plan_required_before_delete") is not True:
        failures.append("Restore plan must be required before delete")

    if policy.get("evidence_preservation_required") is not True:
        failures.append("Evidence preservation must be required")

    required_fields = set(policy.get("required_manifest_fields", []))
    for field in ["file_count", "manifest_digest", "dry_run_only", "restore_verification_required"]:
        if field not in required_fields:
            failures.append(f"Policy missing required manifest field: {field}")

    if audit.get("schema_version") != "clean-slate-backup-restore-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("destructive_delete_performed") is not False:
        failures.append("Audit must confirm no destructive delete")

    plan = build_backup_restore_plan(Path.cwd())
    plan_failures = validate_backup_restore_plan(plan)
    if plan_failures:
        failures.extend(plan_failures)

    if not plan.source_path.endswith(str(DEFAULT_SOURCE)):
        failures.append("Plan source path must target generated_application")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "clean-slate backup",
        "restore",
        "evidence preservation",
        "non-destructive",
        "no generated application files are deleted",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    guard_cli = subprocess.run(
        [
            sys.executable,
            str(PHASE13AF_GUARD),
            "--project-root",
            str(Path.cwd()),
            "--target",
            str(DEFAULT_SOURCE),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if guard_cli.returncode != 0:
        failures.append("Phase 13AF guard must allow generated_application dry-run target")

    planner_cli = subprocess.run(
        [
            sys.executable,
            str(PLANNER_PATH),
            "--project-root",
            str(Path.cwd()),
            "--source",
            str(DEFAULT_SOURCE),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if planner_cli.returncode != 0:
        failures.append("Phase 13AG planner CLI failed")
    elif "clean-slate-backup-restore-plan.v1" not in planner_cli.stdout:
        failures.append("Phase 13AG planner CLI did not emit expected schema")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AG validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AG clean-slate backup/restore artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
