#!/usr/bin/env python3
"""Non-destructive clean-slate regeneration preflight orchestrator."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.build_clean_slate_backup_restore_plan import (  # noqa: E402
    build_backup_restore_plan,
    validate_backup_restore_plan,
)
from scripts.guard_clean_slate_regeneration import (  # noqa: E402
    SafetyDecision,
    build_clean_slate_safety_plan,
    validate_plans as validate_guard_plans,
)
from scripts.validate_clean_slate_human_approval import (  # noqa: E402
    ApprovalValidationResult,
    validate_approval_file,
)


PREFLIGHT_READY = "PREFLIGHT_READY_NON_DESTRUCTIVE"
BLOCKED_APPROVAL = "BLOCKED_APPROVAL_TOKEN_REQUIRED"
BLOCKED_GUARD_OR_BACKUP = "BLOCKED_GUARD_OR_BACKUP_FAILURE"


@dataclass(frozen=True)
class CleanSlatePreflightReport:
    """One non-destructive clean-slate regeneration preflight report."""

    app_id: str
    readiness_status: str
    project_root: str
    destructive_delete_performed: bool
    regeneration_performed: bool
    dry_run_only: bool
    guard_allowed: bool
    backup_restore_valid: bool
    approval_token_present: bool
    approval_token_valid: bool
    approval_errors: tuple[str, ...]
    evidence_preservation_paths: tuple[str, ...]
    backup_manifest_digest: str
    backup_file_count: int
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.readiness_status == PREFLIGHT_READY

    def to_audit_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema_version"] = "clean-slate-regeneration-preflight-report.v1"
        payload["ready"] = self.ready
        return payload


def _approval_result(approval_token: Path | None) -> ApprovalValidationResult:
    if approval_token is None:
        return ApprovalValidationResult(
            valid=False,
            errors=("Human approval token is required for clean-slate preflight readiness.",),
        )
    return validate_approval_file(approval_token)


def build_clean_slate_preflight_report(
    project_root: Path,
    approval_token: Path | None = None,
) -> CleanSlatePreflightReport:
    """Build a non-destructive clean-slate regeneration preflight report."""

    root = project_root.resolve()
    guard_plan = build_clean_slate_safety_plan(root)
    backup_plan = build_backup_restore_plan(root)
    approval = _approval_result(approval_token)

    guard_failures = validate_guard_plans([guard_plan])
    backup_failures = validate_backup_restore_plan(backup_plan)

    guard_allowed = guard_plan.decision == SafetyDecision.ALLOW_DRY_RUN_PLAN.value and not guard_failures
    backup_valid = not backup_failures
    approval_present = approval_token is not None
    approval_valid = approval.valid

    reasons: list[str] = []
    reasons.extend(guard_plan.reasons)
    reasons.extend(guard_failures)
    reasons.extend(backup_failures)
    reasons.extend(approval.errors)

    if not guard_allowed or not backup_valid:
        readiness = BLOCKED_GUARD_OR_BACKUP
    elif not approval_valid:
        readiness = BLOCKED_APPROVAL
    else:
        readiness = PREFLIGHT_READY
        reasons.append("Clean-slate preflight is ready for a future separately gated non-destructive dry run.")

    return CleanSlatePreflightReport(
        app_id="upi_dispute_resolution",
        readiness_status=readiness,
        project_root=str(root),
        destructive_delete_performed=False,
        regeneration_performed=False,
        dry_run_only=True,
        guard_allowed=guard_allowed,
        backup_restore_valid=backup_valid,
        approval_token_present=approval_present,
        approval_token_valid=approval_valid,
        approval_errors=approval.errors,
        evidence_preservation_paths=backup_plan.evidence_preservation_paths,
        backup_manifest_digest=backup_plan.manifest_digest,
        backup_file_count=backup_plan.file_count,
        reasons=tuple(reasons),
    )


def write_preflight_report(report: CleanSlatePreflightReport, audit_out: Path) -> None:
    """Write deterministic JSON audit for a preflight report."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(report.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run non-destructive clean-slate regeneration preflight.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    report = build_clean_slate_preflight_report(args.project_root, args.approval_token)

    if args.audit_out is not None:
        write_preflight_report(report, args.audit_out)

    print(json.dumps(report.to_audit_dict(), indent=2, sort_keys=True))
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
