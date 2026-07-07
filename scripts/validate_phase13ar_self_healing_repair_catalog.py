#!/usr/bin/env python3
"""Validate Phase 13AR governed self-healing repair catalog artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    root_for_path = Path(__file__).resolve().parents[1]
    if str(root_for_path) not in sys.path:
        sys.path.insert(0, str(root_for_path))

from scripts.build_governed_self_healing_repair_catalog import (  # noqa: E402
    BLOCKED,
    CATALOG_ITEMS,
    READY,
    build_governed_repair_catalog,
    validate_governed_repair_catalog,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402

POLICY_PATH = Path("policies/phase13ar_governed_self_healing_repair_catalog_policy.json")
DOC_PATH = Path("docs/phase13ar/governed_self_healing_repair_catalog.md")
CATALOG_PATH = Path("scripts/build_governed_self_healing_repair_catalog.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ar/governed_self_healing_repair_catalog_audit.json"
)
PHASE13AQ_PACK = Path("scripts/build_fresh_recipient_handover_replay_pack.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, CATALOG_PATH, AUDIT_PATH, PHASE13AQ_PACK]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-self-healing-repair-catalog-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_REPAIR_CATALOG_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13aq_fresh_recipient_replay") is not True:
        failures.append("Policy must require Phase 13AQ replay")

    false_keys = [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
        "automatic_repair_application_allowed_in_this_phase",
        "factory_self_modification_allowed_in_this_phase",
    ]
    for key in false_keys:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("required_repair_catalog_items", [])) != set(CATALOG_ITEMS):
        failures.append("Policy catalog items do not match builder catalog items")

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

    audit_false_keys = [
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
    ]
    for key in audit_false_keys:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_catalog = build_governed_repair_catalog(Path.cwd())
    if blocked_catalog.catalog_status != BLOCKED:
        failures.append(f"Catalog without token should be blocked; got {blocked_catalog.catalog_status}")
    failures.extend(validate_governed_repair_catalog(blocked_catalog))

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")
        ready_catalog = build_governed_repair_catalog(Path.cwd(), token_path, True)
        if ready_catalog.catalog_status != READY:
            failures.append(f"Catalog with token should be ready; got {ready_catalog.catalog_status}")
        failures.extend(validate_governed_repair_catalog(ready_catalog))

        cli = subprocess.run(
            [
                sys.executable,
                str(CATALOG_PATH),
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
            failures.append("Repair catalog CLI should pass with token and confirmation")
        elif READY not in cli.stdout:
            failures.append("Repair catalog CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(CATALOG_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Repair catalog CLI without token should exit 2")
    elif BLOCKED not in blocked_cli.stdout:
        failures.append("Repair catalog CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed self-healing repair catalog",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not apply factory self-healing repairs",
        "does not apply factory self-modifications",
        "repair class id",
        "risk tier",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AR validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 13AR governed self-healing repair catalog artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
