#!/usr/bin/env python3
"""Validate Phase 13AH clean-slate human approval artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.validate_clean_slate_human_approval import (  # noqa: E402
    APPROVAL_OPERATION,
    APPROVAL_SCHEMA_VERSION,
    APPROVAL_TARGET_PATH,
    REQUIRED_ACKNOWLEDGEMENTS,
    approval_template,
    validate_approval_payload,
)


POLICY_PATH = Path("policies/phase13ah_clean_slate_human_approval_policy.json")
DOC_PATH = Path("docs/phase13ah/clean_slate_human_approval_workflow.md")
APPROVAL_VALIDATOR_PATH = Path("scripts/validate_clean_slate_human_approval.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ah/clean_slate_human_approval_audit.json"
)
PHASE13AF_GUARD = Path("scripts/guard_clean_slate_regeneration.py")
PHASE13AG_PLANNER = Path("scripts/build_clean_slate_backup_restore_plan.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _valid_sample_token() -> dict[str, object]:
    token = approval_template()
    token["approved_by"] = "local-human-operator"
    token["approval_reason"] = "Controlled validation sample for Phase 13AH tests."
    token["approved_at_utc"] = "2099-01-01T00:00:00Z"
    return token


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, APPROVAL_VALIDATOR_PATH, AUDIT_PATH, PHASE13AF_GUARD, PHASE13AG_PLANNER]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "clean-slate-human-approval-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_NON_DESTRUCTIVE_APPROVAL_TOKEN_GATE":
        failures.append("Policy mode mismatch")

    if policy.get("destructive_delete_allowed_in_this_phase") is not False:
        failures.append("Phase 13AH must not allow destructive delete")

    if policy.get("approval_token_schema") != APPROVAL_SCHEMA_VERSION:
        failures.append("Approval token schema mismatch")

    if policy.get("approval_operation") != APPROVAL_OPERATION:
        failures.append("Approval operation mismatch")

    if policy.get("approval_target_path") != APPROVAL_TARGET_PATH:
        failures.append("Approval target path mismatch")

    required_acknowledgements = set(policy.get("required_acknowledgements", []))
    if not REQUIRED_ACKNOWLEDGEMENTS.issubset(required_acknowledgements):
        failures.append("Policy missing required acknowledgement(s)")

    if audit.get("schema_version") != "clean-slate-human-approval-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("destructive_delete_performed") is not False:
        failures.append("Audit must confirm no destructive delete")

    empty_template_result = validate_approval_payload(approval_template())
    if empty_template_result.valid:
        failures.append("Blank approval template must not validate as approved")

    valid_result = validate_approval_payload(_valid_sample_token())
    if not valid_result.valid:
        failures.append(f"Valid sample token failed validation: {valid_result.errors}")

    wrong_target = _valid_sample_token()
    wrong_target["target_path"] = "docs"
    wrong_target_result = validate_approval_payload(wrong_target)
    if wrong_target_result.valid:
        failures.append("Wrong target token must fail validation")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "clean-slate human approval",
        "non-destructive",
        "human approval token",
        "generated_application",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    template_cli = subprocess.run(
        [sys.executable, str(APPROVAL_VALIDATOR_PATH), "--emit-template"],
        check=False,
        text=True,
        capture_output=True,
    )
    if template_cli.returncode != 0:
        failures.append("Approval validator template CLI failed")
    elif APPROVAL_SCHEMA_VERSION not in template_cli.stdout:
        failures.append("Approval validator template CLI did not emit expected schema")

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(_valid_sample_token(), indent=2), encoding="utf-8")
        token_cli = subprocess.run(
            [sys.executable, str(APPROVAL_VALIDATOR_PATH), "--approval-token", str(token_path)],
            check=False,
            text=True,
            capture_output=True,
        )
        if token_cli.returncode != 0:
            failures.append("Approval validator CLI should pass valid sample token")
        elif '"valid": true' not in token_cli.stdout:
            failures.append("Approval validator CLI did not report valid sample token")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AH validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AH clean-slate human approval artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
