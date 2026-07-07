#!/usr/bin/env python3
"""Validate clean-slate regeneration human approval tokens.

Phase 13AH is non-destructive. This module validates the approval token shape
that a future destructive clean-slate regeneration workflow must require.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


APP_ID = "upi_dispute_resolution"
APPROVAL_SCHEMA_VERSION = "clean-slate-human-approval.v1"
APPROVAL_OPERATION = "CLEAN_SLATE_GENERATED_APPLICATION_REGENERATION"
APPROVAL_TARGET_PATH = "workspace/factory_generated/upi_dispute_resolution/generated_application"

REQUIRED_ACKNOWLEDGEMENTS: frozenset[str] = frozenset(
    {
        "ACK_TARGET_LIMITED_TO_GENERATED_APPLICATION",
        "ACK_BACKUP_RESTORE_PLAN_REQUIRED",
        "ACK_EVIDENCE_PRESERVATION_REQUIRED",
        "ACK_REGENERATION_REVALIDATION_REQUIRED",
        "ACK_RELEASE_REMAINS_HUMAN_GATED",
    }
)

REQUIRED_TEXT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "app_id",
    "operation",
    "target_path",
    "approved_by",
    "approval_reason",
    "approved_at_utc",
    "guard_plan_ref",
    "backup_restore_plan_ref",
    "evidence_preservation_ref",
)


@dataclass(frozen=True)
class ApprovalValidationResult:
    """Human approval-token validation result."""

    valid: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def approval_template() -> dict[str, object]:
    """Return a deterministic approval-token template.

    The template is intentionally not pre-approved because approved_by and
    approved_at_utc must be filled by a human in a future destructive phase.
    """

    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "app_id": APP_ID,
        "operation": APPROVAL_OPERATION,
        "target_path": APPROVAL_TARGET_PATH,
        "approved_by": "",
        "approval_reason": "",
        "approved_at_utc": "",
        "guard_plan_ref": "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13af/clean_slate_regeneration_safety_audit.json",
        "backup_restore_plan_ref": "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ag/clean_slate_backup_restore_audit.json",
        "evidence_preservation_ref": "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts",
        "acknowledgements": sorted(REQUIRED_ACKNOWLEDGEMENTS),
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Approval token must be a JSON object")
    return value


def _string_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _acknowledgements(payload: dict[str, Any]) -> set[str]:
    value = payload.get("acknowledgements")
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def validate_approval_payload(payload: dict[str, Any]) -> ApprovalValidationResult:
    """Validate an approval-token payload."""

    errors: list[str] = []

    for field in REQUIRED_TEXT_FIELDS:
        if not _string_value(payload, field):
            errors.append(f"Missing or empty required field: {field}")

    if _string_value(payload, "schema_version") != APPROVAL_SCHEMA_VERSION:
        errors.append("Invalid schema_version")

    if _string_value(payload, "app_id") != APP_ID:
        errors.append("Invalid app_id")

    if _string_value(payload, "operation") != APPROVAL_OPERATION:
        errors.append("Invalid operation")

    if _string_value(payload, "target_path") != APPROVAL_TARGET_PATH:
        errors.append("Invalid target_path")

    acknowledgements = _acknowledgements(payload)
    missing_acknowledgements = sorted(REQUIRED_ACKNOWLEDGEMENTS.difference(acknowledgements))
    for acknowledgement in missing_acknowledgements:
        errors.append(f"Missing acknowledgement: {acknowledgement}")

    return ApprovalValidationResult(valid=not errors, errors=tuple(errors))


def validate_approval_file(path: Path) -> ApprovalValidationResult:
    """Validate an approval-token file."""

    try:
        payload = _read_json_object(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return ApprovalValidationResult(valid=False, errors=(f"Could not read approval token: {exc}",))
    return validate_approval_payload(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate clean-slate human approval token.")
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--emit-template", action="store_true")
    args = parser.parse_args()

    if args.emit_template:
        print(json.dumps(approval_template(), indent=2, sort_keys=True))
        return 0

    if args.approval_token is None:
        print("ERROR: --approval-token is required unless --emit-template is used", file=sys.stderr)
        return 1

    result = validate_approval_file(args.approval_token)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
