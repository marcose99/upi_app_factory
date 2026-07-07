#!/usr/bin/env python3
"""Validate Phase 13AN controlled real clean-slate application engineering harness."""

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

from scripts.controlled_real_clean_slate_application_engineering import (  # noqa: E402
    HARNESS_BLOCKED,
    HARNESS_READY,
    build_controlled_harness_report,
    validate_controlled_harness_report,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402


POLICY_PATH = Path("policies/phase13an_controlled_real_clean_slate_application_engineering_policy.json")
DOC_PATH = Path("docs/phase13an/controlled_real_clean_slate_application_engineering_harness.md")
HARNESS_PATH = Path("scripts/controlled_real_clean_slate_application_engineering.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13an/controlled_real_clean_slate_application_engineering_audit.json"
)
PHASE13AM_GATE = Path("scripts/gate_real_clean_slate_application_engineering.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, HARNESS_PATH, AUDIT_PATH, PHASE13AM_GATE]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "controlled-real-clean-slate-application-engineering-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_CONTROLLED_HARNESS_DRY_RUN_ONLY":
        failures.append("Policy mode mismatch")

    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    if policy.get("requires_phase13am_execution_gate") is not True:
        failures.append("Policy must require Phase 13AM execution gate")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if policy.get("dry_run_default") is not True:
        failures.append("Policy must make dry-run default")

    blocked_actions = set(policy.get("blocked_actions", []))
    for blocked in [
        "delete_real_generated_application",
        "overwrite_real_generated_application",
        "call_live_llm_provider",
        "call_external_system",
        "auto_merge",
        "auto_tag",
        "auto_release",
    ]:
        if blocked not in blocked_actions:
            failures.append(f"Policy missing blocked action: {blocked}")

    if audit.get("schema_version") != "controlled-real-clean-slate-application-engineering-audit.v1":
        failures.append("Invalid audit schema_version")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "destructive_execution_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_report = build_controlled_harness_report(Path.cwd())
    if blocked_report.harness_status != HARNESS_BLOCKED:
        failures.append(f"Harness without token should be blocked; got {blocked_report.harness_status}")
    blocked_failures = validate_controlled_harness_report(blocked_report)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_report = build_controlled_harness_report(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if ready_report.harness_status != HARNESS_READY:
            failures.append(f"Harness with token and operator confirmation should be ready; got {ready_report.harness_status}")

        ready_failures = validate_controlled_harness_report(ready_report)
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
                "--operator-confirms-final-human-approval",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if cli.returncode != 0:
            failures.append("Controlled harness CLI should pass with valid token and operator confirmation")
        elif HARNESS_READY not in cli.stdout:
            failures.append("Controlled harness CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Controlled harness CLI without token should exit 2")
    elif HARNESS_BLOCKED not in blocked_cli.stdout:
        failures.append("Controlled harness CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "controlled real clean-slate application engineering harness",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not call live providers",
        "execution package",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AN validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AN controlled real clean-slate application engineering harness artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
