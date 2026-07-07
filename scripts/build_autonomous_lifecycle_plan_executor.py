#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_governed_autonomy_control_plane import decide_autonomy_action


APP_ID = "upi_dispute_resolution"
READY = "AUTONOMOUS_LIFECYCLE_PLAN_READY"

REQUIRED_STEP_IDS: tuple[str, ...] = (
    "requirement_intake_preview",
    "domain_analysis_plan",
    "architecture_plan",
    "sandbox_generation_plan",
    "validation_plan",
    "self_healing_plan",
    "evidence_packaging_plan",
    "handover_replay_plan",
    "worktree_promotion_gate",
    "release_candidate_gate",
)


@dataclass(frozen=True)
class LifecyclePlanStep:
    step_id: str
    title: str
    lifecycle_activity: str
    action_id: str
    command_preview: str
    execution_enabled: bool
    decision: dict[str, object]
    evidence_required: tuple[str, ...]
    human_approval_boundary: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "command_preview": self.command_preview,
            "decision": self.decision,
            "evidence_required": list(self.evidence_required),
            "execution_enabled": self.execution_enabled,
            "human_approval_boundary": self.human_approval_boundary,
            "lifecycle_activity": self.lifecycle_activity,
            "step_id": self.step_id,
            "summary": self.summary,
            "title": self.title,
        }


def _decision(
    action_id: str,
    autonomy_level: int,
    human_approved: bool = False,
    sandbox_evidence_present: bool = False,
    policy_evidence_present: bool = True,
) -> dict[str, object]:
    return decide_autonomy_action(
        action_id=action_id,
        requested_autonomy_level=autonomy_level,
        human_approved=human_approved,
        sandbox_evidence_present=sandbox_evidence_present,
        policy_evidence_present=policy_evidence_present,
    ).to_dict()


def _step(
    step_id: str,
    title: str,
    lifecycle_activity: str,
    action_id: str,
    command_preview: str,
    autonomy_level: int,
    evidence_required: tuple[str, ...],
    human_approval_boundary: str,
    summary: str,
    human_approved: bool = False,
    sandbox_evidence_present: bool = False,
) -> LifecyclePlanStep:
    return LifecyclePlanStep(
        step_id=step_id,
        title=title,
        lifecycle_activity=lifecycle_activity,
        action_id=action_id,
        command_preview=command_preview,
        execution_enabled=False,
        decision=_decision(
            action_id,
            autonomy_level,
            human_approved=human_approved,
            sandbox_evidence_present=sandbox_evidence_present,
        ),
        evidence_required=evidence_required,
        human_approval_boundary=human_approval_boundary,
        summary=summary,
    )


def build_autonomous_lifecycle_plan(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    autonomy_level: int = 4,
) -> dict[str, object]:
    steps = (
        _step(
            "requirement_intake_preview",
            "Requirement Intake Preview",
            "requirement_intake",
            "BUILD_REQUIREMENT_PREVIEW",
            "python scripts/build_guided_requirement_intake_preview.py --payload-json '<payload>'",
            autonomy_level,
            ("requirement_preview_json", "policy_evidence"),
            "not_required_for_preview",
            "Normalize requirement intake into deterministic preview.",
        ),
        _step(
            "domain_analysis_plan",
            "Domain Analysis Plan",
            "domain_analysis",
            "VIEW_FACTORY_STATUS",
            "python scripts/build_operator_portal_dashboard_panels.py",
            autonomy_level,
            ("domain_context_summary", "standards_control_matrix"),
            "not_required_for_read_only",
            "Plan domain analysis from existing evidence and standards context.",
        ),
        _step(
            "architecture_plan",
            "Architecture Plan",
            "architecture_design",
            "VIEW_FACTORY_STATUS",
            "python scripts/build_local_operator_portal_status.py",
            autonomy_level,
            ("architecture_decision_record", "mock_boundary_record"),
            "not_required_for_read_only",
            "Plan architecture work without mutating the factory.",
        ),
        _step(
            "sandbox_generation_plan",
            "Sandbox Generation Plan",
            "sandbox_generation",
            "GENERATE_IN_SANDBOX",
            "python scripts/governed_phase_runner.py --phase 14B --gate-name sandbox-generation",
            autonomy_level,
            ("sandbox_manifest", "policy_evidence", "rollback_plan"),
            "not_required_for_sandbox_only",
            "Plan sandbox-only application engineering.",
        ),
        _step(
            "validation_plan",
            "Validation Plan",
            "sandbox_validation",
            "RUN_TESTS",
            "python -m pytest",
            autonomy_level,
            ("pytest_report", "ruff_report", "mypy_report"),
            "not_required_for_validation",
            "Plan local validation without release actions.",
        ),
        _step(
            "self_healing_plan",
            "Self-Healing Plan",
            "self_healing",
            "SELF_HEAL_LOW_RISK_IN_SANDBOX",
            "python scripts/apply_governed_low_risk_repair.py --sandbox",
            autonomy_level,
            ("repair_catalog_match", "sandbox_evidence", "rollback_plan"),
            "not_required_for_low_risk_sandbox_repair",
            "Plan low-risk self-healing in sandbox only.",
        ),
        _step(
            "evidence_packaging_plan",
            "Evidence Packaging Plan",
            "evidence_packaging",
            "VIEW_FACTORY_STATUS",
            "python scripts/build_operator_portal_dashboard_panels.py --audit-out '<path>'",
            autonomy_level,
            ("evidence_manifest", "audit_json"),
            "not_required_for_read_only",
            "Plan deterministic evidence packaging.",
        ),
        _step(
            "handover_replay_plan",
            "Handover Replay Plan",
            "handover_replay",
            "RUN_VALIDATORS",
            "python scripts/validate_phase13aq_fresh_recipient_replay.py",
            autonomy_level,
            ("handover_replay_report", "fresh_recipient_evidence"),
            "not_required_for_validation",
            "Plan handover replay validation.",
        ),
        _step(
            "worktree_promotion_gate",
            "Worktree Promotion Gate",
            "worktree_promotion",
            "PROMOTE_SANDBOX_TO_WORKTREE",
            "human-approved promotion command only after sandbox evidence",
            autonomy_level,
            ("sandbox_evidence", "human_approval_record", "rollback_plan"),
            "human_approval_required",
            "Gate real worktree promotion behind sandbox evidence and human approval.",
            sandbox_evidence_present=True,
        ),
        _step(
            "release_candidate_gate",
            "Release Candidate Gate",
            "release_candidate_preparation",
            "PREPARE_RELEASE_CANDIDATE",
            "human-approved release-candidate command only after full validation",
            autonomy_level,
            ("full_validation_report", "release_evidence", "human_approval_record"),
            "human_approval_required",
            "Gate release candidate preparation behind evidence and human approval.",
            sandbox_evidence_present=True,
        ),
    )
    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "autonomy_level": autonomy_level,
        "execution_mode": "PLAN_ONLY",
        "external_system_calls_performed": False,
        "factory_self_modification_applied": False,
        "live_provider_calls_performed": False,
        "plan_only": True,
        "real_command_execution_performed": False,
        "real_generated_application_deleted": False,
        "real_generated_application_overwritten": False,
        "real_worktree_mutated": False,
        "release_action_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "autonomous-lifecycle-plan.v1",
        "status": READY,
        "steps": [step.to_dict() for step in steps],
    }


def validate_autonomous_lifecycle_plan(plan: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if plan.get("schema_version") != "autonomous-lifecycle-plan.v1":
        failures.append("Invalid lifecycle plan schema")
    if plan.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if plan.get("status") != READY:
        failures.append("Lifecycle plan must be ready")
    if plan.get("plan_only") is not True:
        failures.append("Lifecycle plan must be plan-only")
    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "live_provider_calls_performed",
        "real_command_execution_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "real_worktree_mutated",
        "release_action_performed",
    ]:
        if plan.get(key) is not False:
            failures.append(f"{key} must be false")
    steps_value = plan.get("steps")
    if not isinstance(steps_value, list):
        failures.append("Lifecycle plan steps must be listed")
        return failures
    step_ids: set[str] = set()
    statuses: set[str] = set()
    for step in steps_value:
        if not isinstance(step, dict):
            failures.append("Each lifecycle step must be an object")
            continue
        step_id = step.get("step_id")
        if isinstance(step_id, str):
            step_ids.add(step_id)
        if step.get("execution_enabled") is not False:
            failures.append(f"Step {step_id} must not enable execution in Phase 14A")
        decision = step.get("decision")
        if isinstance(decision, dict):
            status = decision.get("status")
            if isinstance(status, str):
                statuses.add(status)
    for step_id in REQUIRED_STEP_IDS:
        if step_id not in step_ids:
            failures.append(f"Missing lifecycle step: {step_id}")
    if "APPROVED" not in statuses:
        failures.append("Lifecycle plan should include approved read-only/sandbox steps")
    if "HUMAN_APPROVAL_REQUIRED" not in statuses:
        failures.append("Lifecycle plan should include human approval gates")
    return failures


def write_autonomous_lifecycle_plan(plan: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build plan-only autonomous lifecycle plan.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--autonomy-level", type=int, default=4)
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    plan = build_autonomous_lifecycle_plan(args.requirement_id, args.autonomy_level)
    if args.audit_out is not None:
        write_autonomous_lifecycle_plan(plan, args.audit_out)
    print(json.dumps(plan, indent=2, sort_keys=True))
    failures = validate_autonomous_lifecycle_plan(plan)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
