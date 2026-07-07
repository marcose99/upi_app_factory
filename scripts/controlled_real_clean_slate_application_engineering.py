#!/usr/bin/env python3
"""Controlled real clean-slate application engineering harness.

Phase 13AN intentionally remains dry-run only. It builds an auditable execution
package for a later separately approved destructive phase, but does not delete
or overwrite the real generated application.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.build_clean_slate_backup_restore_plan import build_backup_restore_plan  # noqa: E402
from scripts.gate_real_clean_slate_application_engineering import (  # noqa: E402
    READY,
    build_execution_gate_report,
)


APP_ID = "upi_dispute_resolution"
REAL_GENERATED_APPLICATION = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application"
)

HARNESS_READY = "CONTROLLED_HARNESS_READY_DRY_RUN_ONLY"
HARNESS_BLOCKED = "CONTROLLED_HARNESS_BLOCKED_BY_EXECUTION_GATE"

SEQUENCE: tuple[str, ...] = (
    "verify_execution_gate",
    "capture_pre_state",
    "verify_backup_restore_plan",
    "verify_evidence_preservation",
    "plan_delete_real_generated_application",
    "plan_engineer_application_from_requirement_package",
    "plan_full_post_engineering_certification",
    "plan_handoff_replay",
    "plan_human_merge_tag_release_gate",
)


@dataclass(frozen=True)
class ControlledStep:
    """One controlled harness step."""

    order: int
    name: str
    status: str
    destructive: bool
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "destructive": self.destructive,
            "name": self.name,
            "notes": self.notes,
            "order": self.order,
            "status": self.status,
        }


@dataclass(frozen=True)
class ControlledHarnessReport:
    """Controlled real clean-slate application engineering harness report."""

    app_id: str
    harness_status: str
    preferred_term: str
    project_root: str
    real_generated_application_path: str
    real_generated_application_exists: bool
    dry_run_only: bool
    execution_gate_ready: bool
    approval_token_present: bool
    operator_confirmation_present: bool
    execution_package_digest: str
    backup_manifest_digest: str
    planned_steps: tuple[ControlledStep, ...]
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    destructive_execution_performed: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    future_destructive_phase_required: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.harness_status == HARNESS_READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "approval_token_present": self.approval_token_present,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "backup_manifest_digest": self.backup_manifest_digest,
            "destructive_execution_performed": self.destructive_execution_performed,
            "dry_run_only": self.dry_run_only,
            "execution_gate_ready": self.execution_gate_ready,
            "execution_package_digest": self.execution_package_digest,
            "external_system_calls_performed": self.external_system_calls_performed,
            "future_destructive_phase_required": self.future_destructive_phase_required,
            "harness_status": self.harness_status,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "operator_confirmation_present": self.operator_confirmation_present,
            "planned_steps": [step.to_dict() for step in self.planned_steps],
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_exists": self.real_generated_application_exists,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "real_generated_application_path": self.real_generated_application_path,
            "reasons": list(self.reasons),
            "schema_version": "controlled-real-clean-slate-application-engineering-report.v1",
        }


def _resolve_project_path(project_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _planned_steps(ready: bool) -> tuple[ControlledStep, ...]:
    normal_status = "PLANNED" if ready else "BLOCKED"
    steps: list[ControlledStep] = []
    for index, name in enumerate(SEQUENCE, start=1):
        destructive = name in {
            "plan_delete_real_generated_application",
            "plan_engineer_application_from_requirement_package",
        }
        status = "BLOCKED_DRY_RUN_ONLY" if destructive else normal_status
        steps.append(
            ControlledStep(
                order=index,
                name=name,
                status=status,
                destructive=destructive,
                notes="Dry-run plan only; no destructive operation is performed in Phase 13AN.",
            )
        )
    return tuple(steps)


def _digest_package(
    steps: tuple[ControlledStep, ...],
    backup_digest: str,
    gate_ready: bool,
) -> str:
    payload = {
        "backup_manifest_digest": backup_digest,
        "execution_gate_ready": gate_ready,
        "steps": [step.to_dict() for step in steps],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_controlled_harness_report(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> ControlledHarnessReport:
    """Build the controlled dry-run harness report."""

    root = project_root.resolve()
    real_app = _resolve_project_path(root, REAL_GENERATED_APPLICATION)
    execution_gate = build_execution_gate_report(
        project_root=root,
        approval_token=approval_token,
        operator_confirmation=operator_confirmation,
    )
    gate_ready = execution_gate.gate_status == READY
    backup_plan = build_backup_restore_plan(root)

    status = HARNESS_READY if gate_ready else HARNESS_BLOCKED
    reasons: list[str] = list(execution_gate.reasons)

    if gate_ready:
        reasons.append("Controlled harness is ready in dry-run mode only; destructive execution remains blocked.")
    else:
        reasons.append("Controlled harness is blocked because the real execution gate is not ready.")

    steps = _planned_steps(gate_ready)

    return ControlledHarnessReport(
        app_id=APP_ID,
        harness_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        real_generated_application_path=str(real_app),
        real_generated_application_exists=real_app.exists(),
        dry_run_only=True,
        execution_gate_ready=gate_ready,
        approval_token_present=approval_token is not None,
        operator_confirmation_present=operator_confirmation,
        execution_package_digest=_digest_package(steps, backup_plan.manifest_digest, gate_ready),
        backup_manifest_digest=backup_plan.manifest_digest,
        planned_steps=steps,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        destructive_execution_performed=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        future_destructive_phase_required=True,
        reasons=tuple(reasons),
    )


def validate_controlled_harness_report(report: ControlledHarnessReport) -> list[str]:
    """Validate controlled harness safety properties."""

    failures: list[str] = []
    if report.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if not report.dry_run_only:
        failures.append("Phase 13AN harness must be dry-run only")
    if report.destructive_execution_performed:
        failures.append("Phase 13AN must not perform destructive execution")
    if report.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if report.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if report.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if report.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if report.auto_merge_performed or report.auto_tag_performed or report.auto_release_performed:
        failures.append("Phase 13AN must not merge, tag, or release")
    if len(report.execution_package_digest) != 64:
        failures.append("Execution package digest must be SHA-256 hex")
    if len(report.backup_manifest_digest) != 64:
        failures.append("Backup manifest digest must be SHA-256 hex")
    step_names = {step.name for step in report.planned_steps}
    if step_names != set(SEQUENCE):
        failures.append("Controlled harness must include every planned sequence step")
    if not any(step.name == "plan_full_post_engineering_certification" for step in report.planned_steps):
        failures.append("Post-engineering certification must be planned")
    if not any(step.name == "plan_human_merge_tag_release_gate" for step in report.planned_steps):
        failures.append("Human merge/tag/release gate must be planned")
    return failures


def write_controlled_harness_report(report: ControlledHarnessReport, audit_out: Path) -> None:
    """Write deterministic JSON audit for a controlled harness report."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(report.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build controlled clean-slate application engineering harness report.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    report = build_controlled_harness_report(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_controlled_harness_report(report, args.audit_out)

    print(json.dumps(report.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_controlled_harness_report(report)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
