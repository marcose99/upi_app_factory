#!/usr/bin/env python3
"""Plan a non-destructive clean-slate regeneration dry run."""

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


from scripts.run_clean_slate_regeneration_preflight import (  # noqa: E402
    CleanSlatePreflightReport,
    build_clean_slate_preflight_report,
)


DRY_RUN_READY = "DRY_RUN_READY_NON_DESTRUCTIVE"
DRY_RUN_BLOCKED = "DRY_RUN_BLOCKED_BY_PREFLIGHT"


@dataclass(frozen=True)
class DryRunStep:
    """One planned non-destructive clean-slate execution step."""

    order: int
    name: str
    action: str
    destructive: bool
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "destructive": self.destructive,
            "name": self.name,
            "order": self.order,
            "status": self.status,
        }


@dataclass(frozen=True)
class CleanSlateDryRunPlan:
    """Non-destructive dry-run execution plan."""

    app_id: str
    dry_run_status: str
    project_root: str
    dry_run_only: bool
    preflight_ready: bool
    destructive_delete_performed: bool
    regeneration_performed: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    planned_steps: tuple[DryRunStep, ...]
    blocked_actions: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.dry_run_status == DRY_RUN_READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "blocked_actions": list(self.blocked_actions),
            "destructive_delete_performed": self.destructive_delete_performed,
            "dry_run_only": self.dry_run_only,
            "dry_run_status": self.dry_run_status,
            "external_system_calls_performed": self.external_system_calls_performed,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "planned_steps": [step.to_dict() for step in self.planned_steps],
            "preflight_ready": self.preflight_ready,
            "project_root": self.project_root,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "regeneration_performed": self.regeneration_performed,
            "schema_version": "clean-slate-regeneration-dry-run-plan.v1",
        }


def _planned_steps(status: str) -> tuple[DryRunStep, ...]:
    step_status = "PLANNED" if status == DRY_RUN_READY else "BLOCKED"
    return (
        DryRunStep(
            order=1,
            name="run_preflight",
            action="Validate guard, backup/restore, evidence preservation, and approval token.",
            destructive=False,
            status=step_status,
        ),
        DryRunStep(
            order=2,
            name="verify_backup_manifest",
            action="Confirm backup manifest and restore plan are available.",
            destructive=False,
            status=step_status,
        ),
        DryRunStep(
            order=3,
            name="preserve_evidence",
            action="Confirm lifecycle and release evidence are outside deletion scope.",
            destructive=False,
            status=step_status,
        ),
        DryRunStep(
            order=4,
            name="plan_generated_application_delete",
            action="Plan deletion of generated_application only; do not delete in Phase 13AJ.",
            destructive=True,
            status="BLOCKED_NON_DESTRUCTIVE_PHASE",
        ),
        DryRunStep(
            order=5,
            name="plan_regeneration",
            action="Plan regeneration only; do not write regenerated files in Phase 13AJ.",
            destructive=True,
            status="BLOCKED_NON_DESTRUCTIVE_PHASE",
        ),
        DryRunStep(
            order=6,
            name="plan_post_regeneration_certification",
            action="Plan full certification gates after future regeneration.",
            destructive=False,
            status=step_status,
        ),
        DryRunStep(
            order=7,
            name="plan_human_release_gate",
            action="Preserve human approval for merge, tag, and release.",
            destructive=False,
            status=step_status,
        ),
    )


def build_clean_slate_dry_run_plan(
    project_root: Path,
    approval_token: Path | None = None,
) -> CleanSlateDryRunPlan:
    """Build a non-destructive dry-run execution plan."""

    preflight: CleanSlatePreflightReport = build_clean_slate_preflight_report(
        project_root=project_root,
        approval_token=approval_token,
    )
    status = DRY_RUN_READY if preflight.ready else DRY_RUN_BLOCKED
    reasons = tuple(preflight.reasons)

    if preflight.ready:
        reasons = reasons + ("Dry-run execution sequence is ready; destructive actions remain blocked.",)

    return CleanSlateDryRunPlan(
        app_id="upi_dispute_resolution",
        dry_run_status=status,
        project_root=str(project_root.resolve()),
        dry_run_only=True,
        preflight_ready=preflight.ready,
        destructive_delete_performed=False,
        regeneration_performed=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        planned_steps=_planned_steps(status),
        blocked_actions=(
            "delete_generated_application",
            "write_regenerated_application",
            "call_live_llm_provider",
            "call_external_system",
            "auto_merge",
            "auto_tag",
            "auto_release",
        ),
        reasons=reasons,
    )


def validate_dry_run_plan(plan: CleanSlateDryRunPlan) -> list[str]:
    """Validate dry-run plan safety properties."""

    failures: list[str] = []
    if not plan.dry_run_only:
        failures.append("Dry-run plan must remain dry-run only")
    if plan.destructive_delete_performed:
        failures.append("Dry-run plan must not perform deletion")
    if plan.regeneration_performed:
        failures.append("Dry-run plan must not perform regeneration")
    if plan.live_provider_calls_performed:
        failures.append("Dry-run plan must not call live providers")
    if plan.external_system_calls_performed:
        failures.append("Dry-run plan must not call external systems")
    if plan.auto_merge_performed or plan.auto_tag_performed or plan.auto_release_performed:
        failures.append("Dry-run plan must not merge, tag, or release")
    if not any(step.name == "plan_post_regeneration_certification" for step in plan.planned_steps):
        failures.append("Dry-run plan must include post-regeneration certification planning")
    if not any(step.name == "plan_human_release_gate" for step in plan.planned_steps):
        failures.append("Dry-run plan must preserve human release gate")
    return failures


def write_dry_run_plan(plan: CleanSlateDryRunPlan, audit_out: Path) -> None:
    """Write deterministic JSON audit for a dry-run plan."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan clean-slate regeneration dry run.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    plan = build_clean_slate_dry_run_plan(args.project_root, args.approval_token)

    if args.audit_out is not None:
        write_dry_run_plan(plan, args.audit_out)

    print(json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_dry_run_plan(plan)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if plan.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
