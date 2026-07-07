#!/usr/bin/env python3
"""Validate Phase 13AO final clean-slate application engineering readiness pack."""

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

from scripts.assemble_final_clean_slate_application_engineering_readiness_pack import (  # noqa: E402
    BLOCKED,
    READY,
    READINESS_ITEMS,
    assemble_final_readiness_pack,
    validate_final_readiness_pack,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402


POLICY_PATH = Path("policies/phase13ao_final_clean_slate_application_engineering_readiness_policy.json")
DOC_PATH = Path("docs/phase13ao/final_clean_slate_application_engineering_readiness_pack.md")
PACK_PATH = Path("scripts/assemble_final_clean_slate_application_engineering_readiness_pack.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ao/final_clean_slate_application_engineering_readiness_audit.json"
)
PHASE13AN_HARNESS = Path("scripts/controlled_real_clean_slate_application_engineering.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, PACK_PATH, AUDIT_PATH, PHASE13AN_HARNESS]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "final-clean-slate-application-engineering-readiness-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_FINAL_READINESS_PACK_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")

    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    if policy.get("requires_phase13an_controlled_harness") is not True:
        failures.append("Policy must require Phase 13AN controlled harness")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    policy_items = set(policy.get("required_readiness_items", []))
    if policy_items != set(READINESS_ITEMS):
        failures.append("Policy readiness items do not match assembler readiness items")

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

    if audit.get("schema_version") != "final-clean-slate-application-engineering-readiness-audit.v1":
        failures.append("Invalid audit schema_version")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "destructive_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_pack = assemble_final_readiness_pack(Path.cwd())
    if blocked_pack.readiness_status != BLOCKED:
        failures.append(f"Readiness pack without token should be blocked; got {blocked_pack.readiness_status}")
    blocked_failures = validate_final_readiness_pack(blocked_pack)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_pack = assemble_final_readiness_pack(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if ready_pack.readiness_status != READY:
            failures.append(f"Readiness pack with token and confirmation should be ready; got {ready_pack.readiness_status}")

        ready_failures = validate_final_readiness_pack(ready_pack)
        if ready_failures:
            failures.extend(ready_failures)

        cli = subprocess.run(
            [
                sys.executable,
                str(PACK_PATH),
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
            failures.append("Final readiness pack CLI should pass with valid token and operator confirmation")
        elif READY not in cli.stdout:
            failures.append("Final readiness pack CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(PACK_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Final readiness pack CLI without token should exit 2")
    elif BLOCKED not in blocked_cli.stdout:
        failures.append("Final readiness pack CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "final clean-slate application engineering readiness pack",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not call live providers",
        "final non-destructive checkpoint",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AO validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AO final clean-slate application engineering readiness pack artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
