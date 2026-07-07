#!/usr/bin/env python3
"""Validate Phase 13AI clean-slate regeneration preflight artifacts."""

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

from scripts.run_clean_slate_regeneration_preflight import (  # noqa: E402
    BLOCKED_APPROVAL,
    PREFLIGHT_READY,
    build_clean_slate_preflight_report,
)
from scripts.validate_clean_slate_human_approval import approval_template  # noqa: E402


POLICY_PATH = Path("policies/phase13ai_clean_slate_regeneration_preflight_policy.json")
DOC_PATH = Path("docs/phase13ai/clean_slate_regeneration_preflight_orchestrator.md")
ORCHESTRATOR_PATH = Path("scripts/run_clean_slate_regeneration_preflight.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13ai/clean_slate_regeneration_preflight_audit.json"
)
PHASE13AF_GUARD = Path("scripts/guard_clean_slate_regeneration.py")
PHASE13AG_PLANNER = Path("scripts/build_clean_slate_backup_restore_plan.py")
PHASE13AH_APPROVAL = Path("scripts/validate_clean_slate_human_approval.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _valid_sample_token() -> dict[str, object]:
    token = approval_template()
    token["approved_by"] = "local-human-operator"
    token["approval_reason"] = "Controlled validation sample for Phase 13AI tests."
    token["approved_at_utc"] = "2099-01-01T00:00:00Z"
    return token


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, ORCHESTRATOR_PATH, AUDIT_PATH, PHASE13AF_GUARD, PHASE13AG_PLANNER, PHASE13AH_APPROVAL]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "clean-slate-regeneration-preflight-policy.v1":
        failures.append("Invalid policy schema_version")

    if policy.get("mode") != "LOCAL_ONLY_NON_DESTRUCTIVE_PREFLIGHT_ORCHESTRATOR":
        failures.append("Policy mode mismatch")

    if policy.get("destructive_delete_allowed_in_this_phase") is not False:
        failures.append("Phase 13AI must not allow destructive delete")

    if policy.get("regeneration_allowed_in_this_phase") is not False:
        failures.append("Phase 13AI must not allow regeneration")

    for key in [
        "requires_phase13af_guard",
        "requires_phase13ag_backup_restore_plan",
        "requires_phase13ah_human_approval_token",
        "human_approval_required_before_delete",
        "human_approval_required_before_regeneration",
    ]:
        if policy.get(key) is not True:
            failures.append(f"Policy must require {key}")

    if audit.get("schema_version") != "clean-slate-regeneration-preflight-audit.v1":
        failures.append("Invalid audit schema_version")

    if audit.get("destructive_delete_performed") is not False:
        failures.append("Audit must confirm no destructive delete")

    if audit.get("regeneration_performed") is not False:
        failures.append("Audit must confirm no regeneration")

    no_token_report = build_clean_slate_preflight_report(Path.cwd())
    if no_token_report.readiness_status != BLOCKED_APPROVAL:
        failures.append("Preflight without approval token should be blocked for approval")

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(_valid_sample_token(), indent=2), encoding="utf-8")
        valid_report = build_clean_slate_preflight_report(Path.cwd(), token_path)
        if valid_report.readiness_status != PREFLIGHT_READY:
            failures.append(f"Valid preflight should be ready; got {valid_report.readiness_status}")

        cli = subprocess.run(
            [
                sys.executable,
                str(ORCHESTRATOR_PATH),
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
            failures.append("Preflight CLI should pass with valid approval token")
        elif PREFLIGHT_READY not in cli.stdout:
            failures.append("Preflight CLI did not emit ready status")

    blocked_cli = subprocess.run(
        [sys.executable, str(ORCHESTRATOR_PATH), "--project-root", str(Path.cwd())],
        check=False,
        text=True,
        capture_output=True,
    )
    if blocked_cli.returncode != 2:
        failures.append("Preflight CLI without token should exit 2")
    elif BLOCKED_APPROVAL not in blocked_cli.stdout:
        failures.append("Preflight CLI without token did not emit approval-blocked status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "clean-slate regeneration preflight",
        "non-destructive",
        "phase 13af",
        "phase 13ag",
        "phase 13ah",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AI validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AI clean-slate regeneration preflight artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
