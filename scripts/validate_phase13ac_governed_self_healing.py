#!/usr/bin/env python3
"""Validate Phase 13AC governed autonomous self-healing artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


POLICY_PATH = Path("policies/phase13ac_governed_autonomous_self_healing_policy.json")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ac/governed_self_healing_audit.json"
)
DOC_PATH = Path("docs/phase13ac/governed_autonomous_self_healing.md")
CLASSIFIER_PATH = Path("scripts/governed_self_healing.py")

REQUIRED_BLOCKED_CATEGORIES = {
    "UNKNOWN_FAILURE_PATTERN",
    "LIVE_PROVIDER_CALL_REQUIRED",
    "EXTERNAL_SYSTEM_CALL_REQUIRED",
    "POLICY_WEAKENING_REQUIRED",
    "SECURITY_SUPPRESSION_REQUIRED",
    "DEPENDENCY_CHANGE_REQUIRED",
    "DATA_DELETION_REQUIRED",
    "REGULATORY_RULE_CHANGE_REQUIRED",
    "MERGE_TAG_RELEASE_APPROVAL_REQUIRED",
    "SECRETS_OR_CREDENTIALS_EXPOSURE",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, AUDIT_PATH, DOC_PATH, CLASSIFIER_PATH]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-autonomous-self-healing-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_BOUNDED_DETERMINISTIC_REPAIR":
        failures.append("Policy mode must be LOCAL_ONLY_BOUNDED_DETERMINISTIC_REPAIR")

    if policy.get("live_provider_calls_allowed") is not False:
        failures.append("Policy must block live provider calls")

    if policy.get("external_system_calls_allowed") is not False:
        failures.append("Policy must block external system calls")

    if policy.get("human_approval_required_for_release") is not True:
        failures.append("Policy must require human release approval")

    if policy.get("max_repair_iterations") != 5:
        failures.append("Policy must set max_repair_iterations to 5")

    blocked_categories = set(policy.get("blocked_failure_categories", []))
    if not REQUIRED_BLOCKED_CATEGORIES.issubset(blocked_categories):
        failures.append("Policy missing required blocked failure categories")

    if audit.get("schema_version") != "governed-self-healing-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("live_provider_calls_performed") is not False:
        failures.append("Audit must confirm no live provider calls")

    if audit.get("external_system_calls_performed") is not False:
        failures.append("Audit must confirm no external system calls")

    if audit.get("human_approval_required_for_release") is not True:
        failures.append("Audit must require human release approval")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed autonomous self-healing",
        "allowed autonomous repairs",
        "blocked autonomous repairs",
        "human approval",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AC validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AC governed self-healing artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
