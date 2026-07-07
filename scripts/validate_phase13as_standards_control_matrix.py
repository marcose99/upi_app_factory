#!/usr/bin/env python3
"""Validate Phase 13AS local industry standards control matrix artifacts."""

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

from scripts.build_local_industry_standards_control_matrix import (  # noqa: E402
    BLOCKED,
    READY,
    STANDARD_FAMILIES,
    build_local_standards_control_matrix,
    validate_local_standards_control_matrix,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402


POLICY_PATH = Path("policies/phase13as_local_industry_standards_control_matrix_policy.json")
DOC_PATH = Path("docs/phase13as/local_industry_standards_control_matrix.md")
MATRIX_PATH = Path("scripts/build_local_industry_standards_control_matrix.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json"
)
PHASE13AR_CATALOG = Path("scripts/build_governed_self_healing_repair_catalog.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, MATRIX_PATH, AUDIT_PATH, PHASE13AR_CATALOG]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "local-industry-standards-control-matrix-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_STANDARDS_CONTROL_MATRIX_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13ar_repair_catalog") is not True:
        failures.append("Policy must require Phase 13AR repair catalog")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
        "automatic_repair_application_allowed_in_this_phase",
        "factory_self_modification_allowed_in_this_phase",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("required_standard_families", [])) != set(STANDARD_FAMILIES):
        failures.append("Policy standard families do not match matrix standard families")

    blocked_actions = set(policy.get("blocked_actions", []))
    for blocked in [
        "delete_real_generated_application",
        "overwrite_real_generated_application",
        "apply_factory_self_healing_repair",
        "apply_factory_self_modification",
        "call_live_llm_provider",
        "call_external_system",
        "auto_merge",
        "auto_tag",
        "auto_release",
    ]:
        if blocked not in blocked_actions:
            failures.append(f"Policy missing blocked action: {blocked}")

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

    blocked_matrix = build_local_standards_control_matrix(Path.cwd())
    if blocked_matrix.matrix_status != BLOCKED:
        failures.append(f"Matrix without token should be blocked; got {blocked_matrix.matrix_status}")
    blocked_failures = validate_local_standards_control_matrix(blocked_matrix)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_matrix = build_local_standards_control_matrix(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if ready_matrix.matrix_status != READY:
            failures.append(f"Matrix with token and confirmation should be ready; got {ready_matrix.matrix_status}")

        ready_failures = validate_local_standards_control_matrix(ready_matrix)
        if ready_failures:
            failures.extend(ready_failures)

        cli = subprocess.run(
            [
                sys.executable,
                str(MATRIX_PATH),
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
            failures.append("Standards matrix CLI should pass with token and operator confirmation")
        elif READY not in cli.stdout:
            failures.append("Standards matrix CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(MATRIX_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Standards matrix CLI without token should exit 2")
    elif BLOCKED not in blocked_cli.stdout:
        failures.append("Standards matrix CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "local industry standards control matrix",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not apply factory self-healing repairs",
        "does not apply factory self-modifications",
        "local gap elimination rule",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AS validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AS local industry standards control matrix artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
