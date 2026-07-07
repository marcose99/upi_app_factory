#!/usr/bin/env python3
"""Validate Phase 13AP human-approved command pack artifacts."""

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

from scripts.build_human_approved_application_engineering_command_pack import (  # noqa: E402
    BLOCKED,
    COMMAND_ITEMS,
    READY,
    build_human_approved_command_pack,
    validate_human_approved_command_pack,
)
from scripts.propose_factory_self_engineering_improvements import (  # noqa: E402
    build_factory_self_engineering_proposal_pack,
    validate_factory_self_engineering_proposal_pack,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402


POLICY_PATH = Path("policies/phase13ap_human_approved_application_engineering_command_pack_policy.json")
DOC_PATH = Path("docs/phase13ap/human_approved_clean_slate_application_engineering_command_pack.md")
COMMAND_PACK_PATH = Path("scripts/build_human_approved_application_engineering_command_pack.py")
SELF_ENGINEERING_PATH = Path("scripts/propose_factory_self_engineering_improvements.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ap/human_approved_application_engineering_command_pack_audit.json"
)
PHASE13AO_PACK = Path("scripts/assemble_final_clean_slate_application_engineering_readiness_pack.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, COMMAND_PACK_PATH, SELF_ENGINEERING_PATH, AUDIT_PATH, PHASE13AO_PACK]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "human-approved-application-engineering-command-pack-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_COMMAND_PACK_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")

    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    if policy.get("requires_phase13ao_final_readiness_pack") is not True:
        failures.append("Policy must require Phase 13AO final readiness pack")

    if policy.get("factory_self_engineering_proposals_allowed") is not True:
        failures.append("Policy must allow self-engineering proposals")

    if policy.get("factory_self_engineering_auto_apply_allowed") is not False:
        failures.append("Policy must block self-engineering auto-apply")

    policy_items = set(policy.get("required_command_pack_items", []))
    if policy_items != set(COMMAND_ITEMS):
        failures.append("Policy command items do not match builder command items")

    blocked_actions = set(policy.get("blocked_actions", []))
    for blocked in [
        "delete_real_generated_application",
        "overwrite_real_generated_application",
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
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    self_pack = build_factory_self_engineering_proposal_pack(Path.cwd())
    self_failures = validate_factory_self_engineering_proposal_pack(self_pack)
    if self_failures:
        failures.extend(self_failures)

    blocked_pack = build_human_approved_command_pack(Path.cwd())
    if blocked_pack.command_pack_status != BLOCKED:
        failures.append(f"Command pack without token should be blocked; got {blocked_pack.command_pack_status}")
    blocked_failures = validate_human_approved_command_pack(blocked_pack)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_pack = build_human_approved_command_pack(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if ready_pack.command_pack_status != READY:
            failures.append(f"Command pack with token and confirmation should be ready; got {ready_pack.command_pack_status}")

        ready_failures = validate_human_approved_command_pack(ready_pack)
        if ready_failures:
            failures.extend(ready_failures)

        cli = subprocess.run(
            [
                sys.executable,
                str(COMMAND_PACK_PATH),
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
            failures.append("Command pack CLI should pass with valid token and operator confirmation")
        elif READY not in cli.stdout:
            failures.append("Command pack CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(COMMAND_PACK_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Command pack CLI without token should exit 2")
    elif BLOCKED not in blocked_cli.stdout:
        failures.append("Command pack CLI without token did not emit blocked status")

    self_cli = subprocess.run(
        [sys.executable, str(SELF_ENGINEERING_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if self_cli.returncode != 0:
        failures.append("Self-engineering proposal CLI should pass")
    elif "PROPOSALS_ONLY" not in self_cli.stdout:
        failures.append("Self-engineering proposal CLI did not emit proposal-only mode")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "human-approved real clean-slate application engineering command pack",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not apply factory self-modification",
        "governed self-development",
        "governed factory self-engineering proposals",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AP validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AP human-approved command pack and self-engineering proposal artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
