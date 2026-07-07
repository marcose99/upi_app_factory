#!/usr/bin/env python3
"""Validate Phase 13AQ fresh-recipient replay and safe self-healing pack."""

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

from scripts.build_fresh_recipient_handover_replay_pack import (  # noqa: E402
    BLOCKED,
    READY,
    REPLAY_ITEMS,
    build_fresh_recipient_replay_pack,
    validate_fresh_recipient_replay_pack,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402


POLICY_PATH = Path("policies/phase13aq_fresh_recipient_handover_replay_policy.json")
DOC_PATH = Path("docs/phase13aq/fresh_recipient_handover_replay_self_healing_pack.md")
PACK_PATH = Path("scripts/build_fresh_recipient_handover_replay_pack.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13aq/fresh_recipient_handover_replay_audit.json"
)
PHASE13AP_COMMAND = Path("scripts/build_human_approved_application_engineering_command_pack.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, PACK_PATH, AUDIT_PATH, PHASE13AP_COMMAND]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "fresh-recipient-handover-replay-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_FRESH_RECIPIENT_REPLAY_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")

    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    if policy.get("requires_phase13ap_command_pack") is not True:
        failures.append("Policy must require Phase 13AP command pack")

    if policy.get("factory_self_healing_diagnostics_allowed") is not True:
        failures.append("Policy must allow self-healing diagnostics")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
        "factory_self_healing_auto_apply_allowed",
        "factory_self_engineering_auto_apply_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    policy_items = set(policy.get("required_replay_items", []))
    if policy_items != set(REPLAY_ITEMS):
        failures.append("Policy replay items do not match builder replay items")

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

    blocked_pack = build_fresh_recipient_replay_pack(Path.cwd())
    if blocked_pack.replay_status != BLOCKED:
        failures.append(f"Replay pack without token should be blocked; got {blocked_pack.replay_status}")
    blocked_failures = validate_fresh_recipient_replay_pack(blocked_pack)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_pack = build_fresh_recipient_replay_pack(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if ready_pack.replay_status != READY:
            failures.append(f"Replay pack with token and confirmation should be ready; got {ready_pack.replay_status}")

        ready_failures = validate_fresh_recipient_replay_pack(ready_pack)
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
            failures.append("Fresh-recipient replay CLI should pass with token and operator confirmation")
        elif READY not in cli.stdout:
            failures.append("Fresh-recipient replay CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(PACK_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Fresh-recipient replay CLI without token should exit 2")
    elif BLOCKED not in blocked_cli.stdout:
        failures.append("Fresh-recipient replay CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "fresh-recipient handover replay",
        "safe self-healing diagnostics",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not apply factory self-healing repairs",
        "does not apply factory self-modifications",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AQ validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AQ fresh-recipient replay and safe self-healing artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
