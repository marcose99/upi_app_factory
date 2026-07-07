#!/usr/bin/env python3
"""Validate Phase 13AU governed low-risk autonomous repair applier artifacts."""

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

from scripts.apply_governed_low_risk_repair import (  # noqa: E402
    STATUS_APPLIED,
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    LowRiskRepairRequest,
    apply_low_risk_repair,
    validate_low_risk_repair_result,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload  # noqa: E402
from scripts.run_autonomous_phase_engineering import (  # noqa: E402
    READY as RUNNER_READY,
    build_autonomous_phase_engineering_run,
)


POLICY_PATH = Path("policies/phase13au_low_risk_autonomous_repair_policy.json")
DOC_PATH = Path("docs/phase13au/governed_low_risk_autonomous_repair_applier.md")
APPLIER_PATH = Path("scripts/apply_governed_low_risk_repair.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13au/low_risk_autonomous_repair_audit.json"
)
PHASE13AT_RUNNER = Path("scripts/run_autonomous_phase_engineering.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def _write_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def validate() -> list[str]:
    failures: list[str] = []

    for path in [POLICY_PATH, DOC_PATH, APPLIER_PATH, AUDIT_PATH, PHASE13AT_RUNNER]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")

    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "low-risk-autonomous-repair-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "LOCAL_ONLY_LOW_RISK_REPAIR_SANDBOX_NON_DESTRUCTIVE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    if policy.get("requires_phase13at_autonomous_runner") is not True:
        failures.append("Policy must require Phase 13AT autonomous runner")

    for key in [
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "destructive_delete_allowed_in_this_phase",
        "real_generated_application_write_allowed_in_this_phase",
        "automatic_worktree_repair_allowed_without_human_approval",
        "factory_self_modification_allowed_in_this_phase",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    if policy.get("automatic_low_risk_repair_allowed_in_explicit_sandbox") is not True:
        failures.append("Policy must allow explicit sandbox low-risk repairs")

    for key in [
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "project_worktree_modified_by_autonomous_repair",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must confirm {key} is false")

    with tempfile.TemporaryDirectory() as temp_dir:
        token_path = Path(temp_dir) / "approval.json"
        token_path.write_text(json.dumps(sample_approval_token_payload(), indent=2), encoding="utf-8")
        runner = build_autonomous_phase_engineering_run(
            Path.cwd(),
            token_path,
            operator_confirmation=True,
        )
        if runner.runner_status != RUNNER_READY:
            failures.append("Phase 13AT autonomous runner dependency should be ready")

        sandbox = Path(temp_dir) / "sandbox"
        _write_file(sandbox, "docs/example.md", "old phrase\n")
        dry_run = apply_low_risk_repair(
            LowRiskRepairRequest(
                target_root=sandbox,
                relative_path=Path("docs/example.md"),
                repair_class="REPAIR-DOC-001",
                old_text="old phrase",
                new_text="new phrase",
                apply=False,
                sandbox_acknowledged=False,
            )
        )
        if dry_run.repair_status != STATUS_DRY_RUN:
            failures.append("Documentation repair dry-run should be ready")
        if (sandbox / "docs/example.md").read_text(encoding="utf-8") != "old phrase\n":
            failures.append("Dry-run must not mutate sandbox file")
        failures.extend(validate_low_risk_repair_result(dry_run))

        applied = apply_low_risk_repair(
            LowRiskRepairRequest(
                target_root=sandbox,
                relative_path=Path("docs/example.md"),
                repair_class="REPAIR-DOC-001",
                old_text="old phrase",
                new_text="new phrase",
                apply=True,
                sandbox_acknowledged=True,
            )
        )
        if applied.repair_status != STATUS_APPLIED:
            failures.append("Documentation repair should apply in acknowledged sandbox")
        if "new phrase" not in (sandbox / "docs/example.md").read_text(encoding="utf-8"):
            failures.append("Applied sandbox repair did not update file")
        failures.extend(validate_low_risk_repair_result(applied))

        blocked = apply_low_risk_repair(
            LowRiskRepairRequest(
                target_root=sandbox,
                relative_path=Path("workspace/factory_generated/upi_dispute_resolution/generated_application/file.md"),
                repair_class="REPAIR-DOC-001",
                old_text="x",
                new_text="y",
                apply=True,
                sandbox_acknowledged=True,
            )
        )
        if blocked.repair_status != STATUS_BLOCKED:
            failures.append("Protected generated_application path should be blocked")

        cli_target = sandbox / "cli"
        _write_file(cli_target, "docs/cli.md", "alpha\n")
        cli = subprocess.run(
            [
                sys.executable,
                str(APPLIER_PATH),
                "--target-root",
                str(cli_target),
                "--relative-path",
                "docs/cli.md",
                "--repair-class",
                "REPAIR-DOC-001",
                "--old-text",
                "alpha",
                "--new-text",
                "beta",
                "--apply",
                "--sandbox-acknowledged",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if cli.returncode != 0:
            failures.append("Low-risk repair CLI should apply in acknowledged sandbox")
        elif STATUS_APPLIED not in cli.stdout:
            failures.append("Low-risk repair CLI did not emit applied status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "governed low-risk autonomous repair applier",
        "does not delete the real generated application",
        "does not overwrite the real generated application",
        "does not modify the project worktree automatically",
        "does not apply factory self-modifications",
        "allowed repair classes",
        "governance improvement",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 13AU validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Phase 13AU governed low-risk autonomous repair applier artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
