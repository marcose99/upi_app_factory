#!/usr/bin/env python3
"""Validate Phase 13AD governed phase-runner integration artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


POLICY_PATH = Path("policies/phase13ad_governed_phase_runner_integration_policy.json")
DOC_PATH = Path("docs/phase13ad/governed_phase_runner_integration.md")
RUNNER_PATH = Path("scripts/governed_phase_runner.py")
CLASSIFIER_PATH = Path("scripts/governed_self_healing.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ad/governed_phase_runner_integration_audit.json"
)

REQUIRED_GATES = {"ruff", "mypy", "targeted_pytest", "full_pytest"}
REQUIRED_BLOCKED_ACTIONS = {
    "live_provider_call",
    "external_ecosystem_call",
    "policy_weakening",
    "test_gate_bypass",
    "security_suppression",
    "dependency_change_without_review",
    "data_or_evidence_deletion",
    "unknown_autonomous_repair",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, RUNNER_PATH, CLASSIFIER_PATH, AUDIT_PATH]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-phase-runner-integration-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_GOVERNED_PHASE_RUNNER":
        failures.append("Policy mode must be LOCAL_ONLY_GOVERNED_PHASE_RUNNER")

    if policy.get("requires_phase13ac_classifier") is not True:
        failures.append("Policy must require the Phase 13AC classifier")

    if policy.get("live_provider_calls_allowed") is not False:
        failures.append("Policy must block live provider calls")

    if policy.get("external_system_calls_allowed") is not False:
        failures.append("Policy must block external system calls")

    if policy.get("human_approval_required_for_release") is not True:
        failures.append("Policy must require human release approval")

    if set(policy.get("required_gate_names", [])) != REQUIRED_GATES:
        failures.append("Policy required gates mismatch")

    if not REQUIRED_BLOCKED_ACTIONS.issubset(set(policy.get("blocked_actions", []))):
        failures.append("Policy missing blocked actions")

    if audit.get("schema_version") != "governed-phase-runner-integration-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("live_provider_calls_performed") is not False:
        failures.append("Audit must confirm no live provider calls")

    if audit.get("external_system_calls_performed") is not False:
        failures.append("Audit must confirm no external system calls")

    if audit.get("human_approval_required_for_release") is not True:
        failures.append("Audit must require human release approval")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed self-healing integration",
        "phase runners",
        "human approval boundaries",
        "future phase scripts",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "--phase",
            "13AD_VALIDATION",
            "--gate-name",
            "mypy",
            "--failure-text",
            "mypy failed in workspace/generated/foo.py duplicate module named foo",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        failures.append("governed_phase_runner.py CLI failed")
    elif "AUTONOMOUS_REPAIR_ALLOWED" not in result.stdout:
        failures.append("governed_phase_runner.py CLI did not classify known workspace MyPy failure")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AD validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AD governed phase-runner integration artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
