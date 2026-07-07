#!/usr/bin/env python3
"""Validate Phase 13AV local agentic-AI threat-test artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_local_agentic_ai_threat_tests import (  # noqa: E402
    EXPECTED_CONTROLS,
    READY,
    THREAT_FAMILIES,
    build_local_agentic_ai_threat_test_suite,
    validate_threat_test_suite,
)


POLICY_PATH = Path("policies/phase13av_local_agentic_ai_threat_test_policy.json")
DOC_PATH = Path("docs/phase13av/local_agentic_ai_threat_test_suite.md")
SUITE_PATH = Path("scripts/build_local_agentic_ai_threat_tests.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13av/local_agentic_ai_threat_test_audit.json"
)
PHASE13AU_APPLIER = Path("scripts/apply_governed_low_risk_repair.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, SUITE_PATH, AUDIT_PATH, PHASE13AU_APPLIER]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "local-agentic-ai-threat-test-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_DETERMINISTIC_AGENTIC_AI_THREAT_TESTS_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13au_low_risk_repair_applier") is not True:
        failures.append("Policy must require Phase 13AU repair applier")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
        "factory_self_modification_allowed_in_this_phase",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if set(policy.get("required_threat_families", [])) != set(THREAT_FAMILIES):
        failures.append("Policy threat families do not match suite families")

    if set(policy.get("required_control_expectations", [])) != set(EXPECTED_CONTROLS):
        failures.append("Policy controls do not match suite controls")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    suite = build_local_agentic_ai_threat_test_suite(Path.cwd())
    if suite.suite_status != READY:
        failures.append(f"Threat suite should be ready; got {suite.suite_status}")

    suite_failures = validate_threat_test_suite(suite)
    if suite_failures:
        failures.extend(suite_failures)

    cli = subprocess.run(
        [sys.executable, str(SUITE_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Threat-test CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Threat-test CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "local agentic ai threat-test suite",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not call live providers",
        "does not call external systems",
        "does not apply factory self-modifications",
        "threat-test families",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AV validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AV local agentic-AI threat-test artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
