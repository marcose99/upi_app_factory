#!/usr/bin/env python3
"""Real clean-slate application engineering execution gate.

Phase 13AM is intentionally non-destructive. It verifies whether prerequisites
are ready for a future separately approved destructive phase. It never deletes
or overwrites the real generated application.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.run_governed_application_engineering_sandbox import (  # noqa: E402
    build_application_engineering_report,
)


APP_ID = "upi_dispute_resolution"
REAL_GENERATED_APPLICATION = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application"
)

READY = "REAL_EXECUTION_GATE_READY_FOR_FUTURE_HUMAN_APPROVED_PHASE"
BLOCKED_APPROVAL = "REAL_EXECUTION_BLOCKED_APPROVAL_TOKEN_REQUIRED"
BLOCKED_OPERATOR = "REAL_EXECUTION_BLOCKED_OPERATOR_CONFIRMATION_REQUIRED"
BLOCKED_SANDBOX = "REAL_EXECUTION_BLOCKED_APPLICATION_ENGINEERING_SANDBOX"


@dataclass(frozen=True)
class ExecutionGateReport:
    """Real clean-slate application engineering execution-gate report."""

    app_id: str
    gate_status: str
    preferred_term: str
    project_root: str
    real_generated_application_path: str
    real_generated_application_exists: bool
    approval_token_present: bool
    operator_confirmation_present: bool
    application_engineering_sandbox_ready: bool
    destructive_execution_enabled: bool
    destructive_delete_performed: bool
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    future_phase_required: bool
    required_future_gates: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.gate_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "application_engineering_sandbox_ready": self.application_engineering_sandbox_ready,
            "approval_token_present": self.approval_token_present,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "blocked_actions": list(self.blocked_actions),
            "destructive_delete_performed": self.destructive_delete_performed,
            "destructive_execution_enabled": self.destructive_execution_enabled,
            "external_system_calls_performed": self.external_system_calls_performed,
            "future_phase_required": self.future_phase_required,
            "gate_status": self.gate_status,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "operator_confirmation_present": self.operator_confirmation_present,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_exists": self.real_generated_application_exists,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "real_generated_application_path": self.real_generated_application_path,
            "reasons": list(self.reasons),
            "required_future_gates": list(self.required_future_gates),
            "schema_version": "real-clean-slate-application-engineering-execution-gate-report.v1",
        }


def _resolve_project_path(project_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def build_execution_gate_report(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> ExecutionGateReport:
    """Build the real execution-gate report for clean-slate application engineering."""

    root = project_root.resolve()
    real_app = _resolve_project_path(root, REAL_GENERATED_APPLICATION)
    reasons: list[str] = []

    application_engineering = build_application_engineering_report(root, approval_token)
    sandbox_ready = application_engineering.ready

    if not sandbox_ready:
        reasons.append("Application engineering sandbox rehearsal is not ready.")

    approval_present = approval_token is not None
    if not approval_present:
        reasons.append("Human approval token is required.")

    if not operator_confirmation:
        reasons.append("Explicit operator confirmation is required.")

    if not sandbox_ready:
        status = BLOCKED_SANDBOX
    elif not approval_present:
        status = BLOCKED_APPROVAL
    elif not operator_confirmation:
        status = BLOCKED_OPERATOR
    else:
        status = READY
        reasons.append(
            "Execution gate is ready for a future separately approved destructive phase; "
            "Phase 13AM still performs no delete or overwrite."
        )

    return ExecutionGateReport(
        app_id=APP_ID,
        gate_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        real_generated_application_path=str(real_app),
        real_generated_application_exists=real_app.exists(),
        approval_token_present=approval_present,
        operator_confirmation_present=operator_confirmation,
        application_engineering_sandbox_ready=sandbox_ready,
        destructive_execution_enabled=False,
        destructive_delete_performed=False,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        future_phase_required=True,
        required_future_gates=(
            "backup_restore_plan",
            "preflight_ready",
            "dry_run_ready",
            "sandbox_rehearsal_ready",
            "application_engineering_sandbox_ready",
            "human_approval_token",
            "operator_confirmation",
            "post_engineering_certification",
            "human_merge_tag_release_gate",
        ),
        blocked_actions=(
            "delete_real_generated_application",
            "overwrite_real_generated_application",
            "call_live_llm_provider",
            "call_external_system",
            "auto_merge",
            "auto_tag",
            "auto_release",
        ),
        reasons=tuple(reasons),
    )


def validate_execution_gate_report(report: ExecutionGateReport) -> list[str]:
    """Validate execution-gate report safety properties."""

    failures: list[str] = []

    if report.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")

    if report.destructive_execution_enabled:
        failures.append("Phase 13AM must not enable destructive execution")

    if report.destructive_delete_performed:
        failures.append("Phase 13AM must not perform deletion")

    if report.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")

    if report.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")

    if report.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")

    if report.external_system_calls_performed:
        failures.append("External system calls must not occur")

    if report.auto_merge_performed or report.auto_tag_performed or report.auto_release_performed:
        failures.append("Phase 13AM must not merge, tag, or release")

    for required in [
        "human_approval_token",
        "operator_confirmation",
        "post_engineering_certification",
        "human_merge_tag_release_gate",
    ]:
        if required not in report.required_future_gates:
            failures.append(f"Missing required future gate: {required}")

    return failures


def write_execution_gate_report(report: ExecutionGateReport, audit_out: Path) -> None:
    """Write deterministic JSON audit for an execution-gate report."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(report.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate real clean-slate application engineering.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    report = build_execution_gate_report(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_execution_gate_report(report, args.audit_out)

    print(json.dumps(report.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_execution_gate_report(report)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
