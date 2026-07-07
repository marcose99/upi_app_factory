#!/usr/bin/env python3
"""Validate Phase 13AK clean-slate sandbox rehearsal artifacts."""

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

from scripts.rehearse_clean_slate_regeneration_sandbox import (  # noqa: E402
    SANDBOX_RELATIVE_ROOT,
    build_sandbox_rehearsal_report,
    sample_approval_token_payload,
    validate_sandbox_rehearsal_report,
)


POLICY_PATH = Path("policies/phase13ak_clean_slate_sandbox_rehearsal_policy.json")
DOC_PATH = Path("docs/phase13ak/clean_slate_regeneration_sandbox_rehearsal.md")
REHEARSAL_PATH = Path("scripts/rehearse_clean_slate_regeneration_sandbox.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ak/clean_slate_sandbox_rehearsal_audit.json"
)
PHASE13AJ_HARNESS = Path("scripts/plan_clean_slate_regeneration_dry_run.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, REHEARSAL_PATH, AUDIT_PATH, PHASE13AJ_HARNESS]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "clean-slate-sandbox-rehearsal-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_SANDBOX_REHEARSAL":
        failures.append("Policy mode mismatch")

    if policy.get("requires_phase13aj_dry_run_harness") is not True:
        failures.append("Policy must require Phase 13AJ dry-run harness")

    if policy.get("real_generated_application_delete_allowed") is not False:
        failures.append("Policy must block real generated application delete")

    if policy.get("real_generated_application_write_allowed") is not False:
        failures.append("Policy must block real generated application writes")

    if policy.get("sandbox_write_allowed") is not True:
        failures.append("Policy must allow sandbox-only writes")

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

    if audit.get("schema_version") != "clean-slate-sandbox-rehearsal-audit.v1":
        failures.append("Invalid audit schema_version")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    blocked_report = build_sandbox_rehearsal_report(Path.cwd())
    if blocked_report.ready:
        failures.append("Sandbox rehearsal without approval token should not be ready")
    blocked_failures = validate_sandbox_rehearsal_report(blocked_report)
    if blocked_failures:
        failures.extend(blocked_failures)

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")
        ready_report = build_sandbox_rehearsal_report(Path.cwd(), token_path)
        if not ready_report.ready:
            failures.append(f"Sandbox rehearsal with valid token should be ready: {ready_report.reasons}")

        ready_failures = validate_sandbox_rehearsal_report(ready_report)
        if ready_failures:
            failures.extend(ready_failures)

        isolated_root = Path(temp_dir) / "isolated_project"
        isolated_root.mkdir(parents=True)
        isolated_report = build_sandbox_rehearsal_report(
            isolated_root,
            token_path,
            sandbox_root=Path("outside_sandbox"),
        )
        if isolated_report.sandbox_only:
            failures.append("Unapproved sandbox root must not be accepted")

        cli = subprocess.run(
            [
                sys.executable,
                str(REHEARSAL_PATH),
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
            failures.append("Sandbox rehearsal CLI should pass with valid approval token")
        elif "SANDBOX_REHEARSAL_READY" not in cli.stdout:
            failures.append("Sandbox rehearsal CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(REHEARSAL_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Sandbox rehearsal CLI without token should exit 2")
    elif "SANDBOX_REHEARSAL_BLOCKED" not in blocked_cli.stdout:
        failures.append("Sandbox rehearsal CLI without token did not emit blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "clean-slate regeneration sandbox rehearsal",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "sandbox boundary",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    if str(SANDBOX_RELATIVE_ROOT) not in DOC_PATH.read_text(encoding="utf-8"):
        failures.append("Documentation must include the sandbox root")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AK validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AK clean-slate sandbox rehearsal artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
