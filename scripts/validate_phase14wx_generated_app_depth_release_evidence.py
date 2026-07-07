#!/usr/bin/env python3
"""Read-only validator for Phase 14W-X batch artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.run_generated_app_depth_release_evidence_batch import (
    DEFAULT_AUDIT_PATH,
    DOC_PATH,
    POLICY_PATH,
    SCHEMA_VERSION,
    build_generated_app_depth_release_evidence_batch,
)

JsonDict = dict[str, Any]


def _load_json_object(path: Path) -> JsonDict:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(JsonDict, loaded)


def validate_generated_app_depth_release_evidence_batch(audit_path: Path = DEFAULT_AUDIT_PATH) -> list[str]:
    errors: list[str] = []
    for path in (DOC_PATH, POLICY_PATH, audit_path):
        if not path.exists():
            errors.append(f"Missing required artifact: {path}")
    if errors:
        return errors

    expected = build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=False,
        audit_out=Path("/tmp/phase14wx_validator_expected_audit.json"),
    )
    audit = _load_json_object(audit_path)
    policy = _load_json_object(POLICY_PATH)

    if audit.get("schema_version") != SCHEMA_VERSION:
        errors.append("Audit schema version mismatch")
    if audit.get("phase") != "14W-X":
        errors.append("Audit phase must be 14W-X")
    if audit.get("batch_phases") != ["14W", "14X"]:
        errors.append("Batch phases must be 14W and 14X")
    if audit.get("generated_application_depth_roadmap_executor_enabled") is not True:
        errors.append("Generated application depth roadmap executor must be enabled")
    if audit.get("release_evidence_industrialization_enabled") is not True:
        errors.append("Release evidence industrialization must be enabled")
    if audit.get("factory_does_not_self_certify") is not True:
        errors.append("Factory must not self-certify")
    if audit.get("official_certification_claimed") is not False:
        errors.append("Factory must not claim official certification")
    if audit.get("blocked_autonomous_actions") != expected["blocked_autonomous_actions"]:
        errors.append("Blocked autonomous actions mismatch")
    if policy.get("blocked_autonomous_actions") != expected["blocked_autonomous_actions"]:
        errors.append("Policy blocked autonomous actions mismatch")
    if "certifying_authority_review" not in audit.get("what_sits_between_generated_application_and_certification", []):
        errors.append("Certification authority review boundary is missing")
    if audit.get("quality_preserving_fast_path") is None:
        errors.append("Quality-preserving fast path is missing")
    return errors


def main() -> int:
    errors = validate_generated_app_depth_release_evidence_batch()
    if errors:
        print("Phase 14W-X validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Phase 14W-X generated application depth and release evidence artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
