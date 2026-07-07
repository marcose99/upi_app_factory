#!/usr/bin/env python3
"""Validate Phase 13AJ clean-slate regeneration dry-run artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.plan_clean_slate_regeneration_dry_run import (  # noqa: E402
    DRY_RUN_BLOCKED,
    DRY_RUN_READY,
    build_clean_slate_dry_run_plan,
    validate_dry_run_plan,
)
from scripts.validate_clean_slate_human_approval import approval_template  # noqa: E402


POLICY_PATH = Path("policies/phase13aj_clean_slate_regeneration_dry_run_policy.json")
DOC_PATH = Path("docs/phase13aj/clean_slate_regeneration_dry_run_execution_harness.md")
HARNESS_PATH = Path("scripts/plan_clean_slate_regeneration_dry_run.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13aj/clean_slate_regeneration_dry_run_audit.json"
)
PHASE13AI_PREFLIGHT = Path("scripts/run_clean_slate_regeneration_preflight.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def _valid_sample_token() -> dict[str, object]:
    token = approval_template()
    token["approved_by"] = "local-human-operator"
    token["approval_reason"] = "Controlled validation sample for Phase 13AJ tests."
    token["approved_at_utc"] = "2099-01-01T00:00:00Z"
    return token


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, HARNESS_PATH, AUDIT_PATH, PHASE13AI_PREFLIGHT]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "clean-slate-regeneration-dry-run-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_NON_DESTRUCTIVE_DRY_RUN_EXECUTION_HARNESS":
        failures.append("Policy mode mismatch")

    if policy.get("requires_phase13ai_preflight_orchestrator") is not True:
        failures.append("Policy must require Phase 13AI preflight orchestrator")

    if policy.get("destructive_delete_allowed_in_this_phase") is not False:
        failures.append("Phase 13AJ must not allow destructive delete")

    if policy.get("regeneration_allowed_in_this_phase") is not False:
        failures.append("Phase 13AJ must not allow regeneration")

    for blocked in [
        "delete_generated_application",
        "write_regenerated_application",
        "call_live_llm_provider",
        "call_external_system",
        "auto_merge",
        "auto_tag",
        "auto_release",
    ]:
        if blocked not in set(policy.get("blocked_actions", [])):
            failures.append(f"Policy missing blocked action: {blocked}")

    if audit.get("schema_version") != "clean-slate-regeneration-dry-run-audit.v1":
        failures.append("Invalid audit schema_version")

    for key in [
        "destructive_delete_performed",
        "regeneration_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_plan = build_clean_slate_dry_run_plan(Path.cwd())
    if blocked_plan.dry_run_status != DRY_RUN_BLOCKED:
        failures.append("Dry-run without approval token should be blocked by preflight")

    if validate_dry_run_plan(blocked_plan):
        failures.extend(validate_dry_run_plan(blocked_plan))

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(_valid_sample_token(), indent=2), encoding="utf-8")
        ready_plan = build_clean_slate_dry_run_plan(Path.cwd(), token_path)
        if ready_plan.dry_run_status != DRY_RUN_READY:
            failures.append(f"Dry-run with valid token should be ready; got {ready_plan.dry_run_status}")

        ready_failures = validate_dry_run_plan(ready_plan)
        if ready_failures:
            failures.extend(ready_failures)

        cli = subprocess.run(
            [
                sys.executable,
                str(HARNESS_PATH),
                "--project-root",
                str(Path.cwd()),
                "--approval-token",
                str(token_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if cli.returncode != 0:
            failures.append("Dry-run CLI should pass with valid approval token")
        elif DRY_RUN_READY not in cli.stdout:
            failures.append("Dry-run CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Dry-run CLI without token should exit 2")
    elif DRY_RUN_BLOCKED not in blocked_cli.stdout:
        failures.append("Dry-run CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "clean-slate regeneration dry-run execution harness",
        "non-destructive",
        "does not delete",
        "does not regenerate",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AJ validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AJ clean-slate regeneration dry-run artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
