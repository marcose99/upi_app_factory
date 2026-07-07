#!/usr/bin/env python3
"""Validate Phase 13AE governed self-healing adoption gate artifacts."""

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

from scripts.check_governed_self_healing_adoption import evaluate_script_text  # noqa: E402


POLICY_PATH = Path("policies/phase13ae_governed_self_healing_adoption_policy.json")
DOC_PATH = Path("docs/phase13ae/governed_self_healing_adoption_gate.md")
CHECKER_PATH = Path("scripts/check_governed_self_healing_adoption.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ae/governed_self_healing_adoption_audit.json"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, CHECKER_PATH, AUDIT_PATH]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-self-healing-adoption-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_FUTURE_PHASE_SCRIPT_ADOPTION_GATE":
        failures.append("Policy mode mismatch")

    if policy.get("live_provider_calls_allowed") is not False:
        failures.append("Policy must block live provider calls")

    if policy.get("external_system_calls_allowed") is not False:
        failures.append("Policy must block external system calls")

    if policy.get("human_approval_required_for_release") is not True:
        failures.append("Policy must require human release approval")

    if policy.get("equivalent_control_marker") != "GOVERNED_SELF_HEALING_EQUIVALENT_CONTROL":
        failures.append("Policy equivalent control marker mismatch")

    if "skip mypy" not in set(policy.get("blocked_bypass_patterns", [])):
        failures.append("Policy must include blocked bypass patterns")

    if audit.get("schema_version") != "governed-self-healing-adoption-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("live_provider_calls_performed") is not False:
        failures.append("Audit must confirm no live provider calls")

    if audit.get("external_system_calls_performed") is not False:
        failures.append("Audit must confirm no external system calls")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed self-healing adoption gate",
        "every future phase automation script",
        "governed phase runner",
        "equivalent governed control",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    runner_result = evaluate_script_text("python scripts/governed_phase_runner.py --phase 13AF")
    if not runner_result.compliant:
        failures.append("Checker should accept governed runner usage")

    equivalent_result = evaluate_script_text(
        "# GOVERNED_SELF_HEALING_EQUIVALENT_CONTROL\n"
        "# classify failures, unknown failures go to human review, "
        "post-repair gates rerun, audit evidence recorded"
    )
    if not equivalent_result.compliant:
        failures.append("Checker should accept complete equivalent control declaration")

    bypass_result = evaluate_script_text("echo skip mypy and bypass gate")
    if bypass_result.compliant:
        failures.append("Checker must reject blocked bypass patterns")

    with tempfile.TemporaryDirectory() as temp_dir:
        sample = Path(temp_dir) / "phase13af_sample.sh"
        sample.write_text("python scripts/governed_phase_runner.py --phase 13AF\n", encoding="utf-8")
        cli = subprocess.run(
            [sys.executable, str(CHECKER_PATH), "--script", str(sample), "--json"],
            check=False,
            text=True,
            capture_output=True,
        )
        if cli.returncode != 0:
            failures.append("Checker CLI should pass for governed runner sample")
        elif "Script uses the governed phase runner" not in cli.stdout:
            failures.append("Checker CLI did not report governed runner usage")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AE validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AE governed self-healing adoption artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
