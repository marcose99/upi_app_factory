#!/usr/bin/env python3
"""Clean-slate regeneration deletion guard.

This module is intentionally non-destructive in Phase 13AF. It builds and
validates dry-run clean-slate deletion plans for the generated application.

Future phases may add an explicit destructive workflow, but only after passing
this guard and requiring human approval.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


APP_ID = "upi_dispute_resolution"
DEFAULT_GENERATED_APPLICATION = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
DEFAULT_BACKUP_ROOT = Path(
    "workspace/factory_generated/upi_dispute_resolution/clean_slate_backups"
)
LIFECYCLE_ARTIFACTS = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts"
)
RELEASE_HANDOFF = Path(
    "workspace/factory_generated/upi_dispute_resolution/release_handoff"
)


class SafetyDecision(str, Enum):
    """Safety decision for a clean-slate regeneration request."""

    ALLOW_DRY_RUN_PLAN = "ALLOW_DRY_RUN_PLAN"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class CleanSlateSafetyPlan:
    """Dry-run safety plan for future clean-slate regeneration."""

    app_id: str
    target_path: str
    backup_path: str
    decision: str
    dry_run_only: bool
    destructive_delete_performed: bool
    human_approval_required_before_delete: bool
    human_approval_required_before_regeneration: bool
    backup_required: bool
    evidence_preservation_paths: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.decision == SafetyDecision.ALLOW_DRY_RUN_PLAN.value

    def to_audit_dict(self) -> dict[str, object]:
        return asdict(self)


def _resolve_project_path(project_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def build_clean_slate_safety_plan(
    project_root: Path,
    target_path: Path = DEFAULT_GENERATED_APPLICATION,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
) -> CleanSlateSafetyPlan:
    """Build a non-destructive dry-run clean-slate safety plan."""

    root = project_root.resolve()
    target = _resolve_project_path(root, target_path)
    allowed_target = _resolve_project_path(root, DEFAULT_GENERATED_APPLICATION)
    backup = _resolve_project_path(root, backup_root) / "generated_application_backup"

    reasons: list[str] = []
    decision = SafetyDecision.ALLOW_DRY_RUN_PLAN

    if not _is_relative_to(target, root):
        decision = SafetyDecision.BLOCK
        reasons.append("Target path is outside the project root.")

    if target != allowed_target:
        decision = SafetyDecision.BLOCK
        reasons.append("Target path is not the approved generated_application boundary.")

    blocked_roots = [
        root,
        root / ".git",
        root / ".venv",
        root / "docs",
        root / "policies",
        root / "scripts",
        root / "tests",
        root / "factory_governance",
        _resolve_project_path(root, LIFECYCLE_ARTIFACTS),
        _resolve_project_path(root, RELEASE_HANDOFF),
    ]

    for blocked in blocked_roots:
        if target == blocked or _is_relative_to(blocked, target):
            decision = SafetyDecision.BLOCK
            reasons.append(f"Target would include blocked path: {blocked.relative_to(root)}")

    if target.exists() and target.is_symlink():
        decision = SafetyDecision.BLOCK
        reasons.append("Target path is a symlink and is blocked.")

    if not target.exists():
        reasons.append("Target does not currently exist; dry-run plan is still safe.")

    if decision is SafetyDecision.ALLOW_DRY_RUN_PLAN:
        reasons.append("Dry-run plan allowed. Destructive delete remains blocked in Phase 13AF.")

    return CleanSlateSafetyPlan(
        app_id=APP_ID,
        target_path=str(target),
        backup_path=str(backup),
        decision=decision.value,
        dry_run_only=True,
        destructive_delete_performed=False,
        human_approval_required_before_delete=True,
        human_approval_required_before_regeneration=True,
        backup_required=True,
        evidence_preservation_paths=(
            str(_resolve_project_path(root, LIFECYCLE_ARTIFACTS)),
            str(_resolve_project_path(root, RELEASE_HANDOFF)),
        ),
        reasons=tuple(reasons),
    )


def validate_plans(plans: Iterable[CleanSlateSafetyPlan]) -> list[str]:
    """Validate safety plans for internal consistency."""

    failures: list[str] = []
    for plan in plans:
        if not plan.dry_run_only:
            failures.append(f"{plan.target_path}: Phase 13AF plans must be dry-run only")
        if plan.destructive_delete_performed:
            failures.append(f"{plan.target_path}: destructive delete must not be performed")
        if not plan.human_approval_required_before_delete:
            failures.append(f"{plan.target_path}: delete must require human approval")
        if not plan.backup_required:
            failures.append(f"{plan.target_path}: backup must be required")
    return failures


def write_audit_plan(plan: CleanSlateSafetyPlan, audit_out: Path) -> None:
    """Write deterministic JSON audit for a clean-slate safety plan."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clean-slate regeneration safety plan.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--target", type=Path, default=DEFAULT_GENERATED_APPLICATION)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    plan = build_clean_slate_safety_plan(
        project_root=args.project_root,
        target_path=args.target,
        backup_root=args.backup_root,
    )

    failures = validate_plans([plan])
    if args.audit_out is not None:
        write_audit_plan(plan, args.audit_out)

    print(json.dumps(plan.to_audit_dict(), indent=2, sort_keys=True))

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if plan.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
