#!/usr/bin/env python3
"""Validate Phase 13AL governed application engineering artifacts."""

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

from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402
from scripts.run_governed_application_engineering_sandbox import (  # noqa: E402
    ENGINEERING_SANDBOX_RELATIVE_ROOT,
    ENGINEERING_STAGES,
    build_application_engineering_report,
    validate_application_engineering_report,
)


POLICY_PATH = Path("policies/phase13al_governed_autonomous_application_engineering_policy.json")
DOC_PATH = Path("docs/phase13al/governed_autonomous_application_engineering_sandbox_rehearsal.md")
HARNESS_PATH = Path("scripts/run_governed_application_engineering_sandbox.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13al/governed_autonomous_application_engineering_audit.json"
)
PHASE13AK_REHEARSAL = Path("scripts/rehearse_clean_slate_regeneration_sandbox.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, HARNESS_PATH, AUDIT_PATH, PHASE13AK_REHEARSAL]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "governed-autonomous-application-engineering-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_SANDBOX_APPLICATION_ENGINEERING_REHEARSAL":
        failures.append("Policy mode mismatch")

    terminology = policy.get("terminology", {})
    if not isinstance(terminology, dict) or terminology.get("preferred") != "application engineering":
        failures.append("Policy must prefer application engineering terminology")

    if policy.get("requires_phase13ak_sandbox_rehearsal") is not True:
        failures.append("Policy must require Phase 13AK sandbox rehearsal")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "real_generated_application_delete_allowed",
        "real_generated_application_write_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    policy_stages = set(policy.get("engineering_stages", []))
    if policy_stages != set(ENGINEERING_STAGES):
        failures.append("Policy engineering stages do not match harness stages")

    blocked_actions = set(policy.get("blocked_actions", []))
    for blocked in [
        "delete_real_generated_application",
        "overwrite_real_generated_application",
        "call_live_llm_provider",
        "call_external_system",
        "auto_merge",
        "auto_tag",
        "auto_release",
    ]:
        if blocked not in blocked_actions:
            failures.append(f"Policy missing blocked action: {blocked}")

    if audit.get("schema_version") != "governed-autonomous-application-engineering-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("preferred_term") != "application engineering":
        failures.append("Audit must record preferred term as application engineering")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_report = build_application_engineering_report(Path.cwd())
    if blocked_report.ready:
        failures.append("Application engineering rehearsal without approval token should not be ready")
    blocked_failures = validate_application_engineering_report(blocked_report)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")

        ready_report = build_application_engineering_report(Path.cwd(), token_path)
        if not ready_report.ready:
            failures.append(f"Application engineering rehearsal with valid token should be ready: {ready_report.reasons}")

        ready_failures = validate_application_engineering_report(ready_report)
        if ready_failures:
            failures.extend(ready_failures)

        cli = subprocess.run(
            [
                sys.executable,
                str(HARNESS_PATH),
                "--project-root",
                str(Path.cwd()),
                "--approval-token",
                str(token_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if cli.returncode != 0:
            failures.append("Application engineering CLI should pass with valid approval token")
        elif "APPLICATION_ENGINEERING_SANDBOX_READY" not in cli.stdout:
            failures.append("Application engineering CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Application engineering CLI without token should exit 2")
    elif "APPLICATION_ENGINEERING_SANDBOX_BLOCKED" not in blocked_cli.stdout:
        failures.append("Application engineering CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed autonomous application engineering",
        "application engineering",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "requirements -> domain model -> architecture -> design -> implementation -> tests -> security/policy -> certification -> evidence -> handoff",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    if str(ENGINEERING_SANDBOX_RELATIVE_ROOT) not in DOC_PATH.read_text(encoding="utf-8"):
        failures.append("Documentation must include engineering sandbox root")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AL validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AL governed autonomous application engineering artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
