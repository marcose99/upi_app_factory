#!/usr/bin/env python3
"""Validate Phase 13AT autonomous phase engineering runner artifacts."""

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

from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402
from scripts.run_autonomous_phase_engineering import (  # noqa: E402
    BLOCKED,
    BLUEPRINT_ITEMS,
    READY,
    build_autonomous_phase_engineering_run,
    validate_autonomous_phase_engineering_run,
)


POLICY_PATH = Path("policies/phase13at_autonomous_phase_engineering_runner_policy.json")
DOC_PATH = Path("docs/phase13at/autonomous_standards_gap_phase_engineering_runner.md")
RUNNER_PATH = Path("scripts/run_autonomous_phase_engineering.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13at/autonomous_phase_engineering_runner_audit.json"
)
PHASE13AS_MATRIX = Path("scripts/build_local_industry_standards_control_matrix.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, RUNNER_PATH, AUDIT_PATH, PHASE13AS_MATRIX]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "autonomous-phase-engineering-runner-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_AUTONOMOUS_PHASE_PLANNING_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13as_standards_control_matrix") is not True:
        failures.append("Policy must require Phase 13AS standards matrix")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
        "automatic_repair_application_allowed_in_this_phase",
        "factory_self_modification_allowed_in_this_phase",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("required_blueprint_items", [])) != set(BLUEPRINT_ITEMS):
        failures.append("Policy blueprint items do not match runner blueprint items")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "destructive_execution_performed",
        "factory_self_healing_repair_applied",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_run = build_autonomous_phase_engineering_run(Path.cwd())
    if blocked_run.runner_status != BLOCKED:
        failures.append(f"Runner without token should be blocked; got {blocked_run.runner_status}")
    blocked_failures = validate_autonomous_phase_engineering_run(blocked_run)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_run = build_autonomous_phase_engineering_run(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if ready_run.runner_status != READY:
            failures.append(f"Runner with token and confirmation should be ready; got {ready_run.runner_status}")

        ready_failures = validate_autonomous_phase_engineering_run(ready_run)
        if ready_failures:
            failures.extend(ready_failures)

        cli = subprocess.run(
            [
                sys.executable,
                str(RUNNER_PATH),
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
            failures.append("Autonomous runner CLI should pass with token and operator confirmation")
        elif READY not in cli.stdout:
            failures.append("Autonomous runner CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Autonomous runner CLI without token should exit 2")
    elif BLOCKED not in blocked_cli.stdout:
        failures.append("Autonomous runner CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "autonomous standards-gap phase engineering runner",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not apply factory self-healing repairs",
        "does not apply factory self-modifications",
        "what is autonomous in this phase",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AT validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AT autonomous phase engineering runner artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
