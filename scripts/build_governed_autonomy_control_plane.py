#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


APP_ID = "upi_dispute_resolution"
READY = "GOVERNED_A_TO_Z_AUTONOMY_CONTROL_PLANE_READY"


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    SANDBOX_EVIDENCE_REQUIRED = "SANDBOX_EVIDENCE_REQUIRED"
    POLICY_EVIDENCE_REQUIRED = "POLICY_EVIDENCE_REQUIRED"


@dataclass(frozen=True)
class AutonomyAction:
    action_id: str
    lifecycle_activity: str
    risk_tier: str
    minimum_autonomy_level: int
    execution_zone: str
    allowed: bool
    human_approval_required: bool
    sandbox_evidence_required: bool
    policy_evidence_required: bool
    rollback_required: bool
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "allowed": self.allowed,
            "execution_zone": self.execution_zone,
            "human_approval_required": self.human_approval_required,
            "lifecycle_activity": self.lifecycle_activity,
            "minimum_autonomy_level": self.minimum_autonomy_level,
            "policy_evidence_required": self.policy_evidence_required,
            "risk_tier": self.risk_tier,
            "rollback_required": self.rollback_required,
            "sandbox_evidence_required": self.sandbox_evidence_required,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class AutonomyDecision:
    action_id: str
    status: DecisionStatus
    requested_autonomy_level: int
    reasons: tuple[str, ...]
    human_approval_required: bool
    evidence_required: tuple[str, ...]
    execution_zone: str
    mutation_allowed_now: bool
    release_allowed_now: bool
    live_provider_call_allowed_now: bool
    external_system_call_allowed_now: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "evidence_required": list(self.evidence_required),
            "execution_zone": self.execution_zone,
            "external_system_call_allowed_now": self.external_system_call_allowed_now,
            "human_approval_required": self.human_approval_required,
            "live_provider_call_allowed_now": self.live_provider_call_allowed_now,
            "mutation_allowed_now": self.mutation_allowed_now,
            "reasons": list(self.reasons),
            "release_allowed_now": self.release_allowed_now,
            "requested_autonomy_level": self.requested_autonomy_level,
            "status": self.status.value,
        }


AUTONOMY_LEVELS: tuple[dict[str, object], ...] = (
    {"level": 0, "name": "LEVEL_0_MANUAL", "description": "Human runs everything."},
    {"level": 1, "name": "LEVEL_1_GUIDED", "description": "Factory suggests commands and previews outcomes."},
    {"level": 2, "name": "LEVEL_2_READ_ONLY_VALIDATION", "description": "Factory performs read-only checks and evidence summaries."},
    {"level": 3, "name": "LEVEL_3_SANDBOX_AUTONOMOUS", "description": "Factory may generate, validate, and repair in sandbox only."},
    {"level": 4, "name": "LEVEL_4_HUMAN_GATED_WORKTREE_AUTONOMOUS", "description": "Factory may promote approved worktree changes after human gate."},
    {"level": 5, "name": "LEVEL_5_RELEASE_GATED_AUTONOMOUS", "description": "Factory may prepare release candidates; merge/tag/release remain human-gated."},
    {"level": 6, "name": "LEVEL_6_ENTERPRISE_AUTONOMOUS_REFERENCE", "description": "Reference target for enterprise deployment, identity, secrets, provenance, and operations."},
)

LIFECYCLE_ACTIVITIES: tuple[str, ...] = (
    "requirement_intake",
    "domain_analysis",
    "architecture_design",
    "planning",
    "prompt_pack_generation",
    "sandbox_generation",
    "sandbox_validation",
    "security_validation",
    "governance_validation",
    "self_healing",
    "evidence_packaging",
    "handover_replay",
    "worktree_promotion",
    "release_candidate_preparation",
    "merge_tag_release",
)

BLOCKED_ACTIONS: tuple[str, ...] = (
    "ARBITRARY_SHELL_COMMAND",
    "DELETE_REAL_GENERATED_APPLICATION",
    "OVERWRITE_REAL_GENERATED_APPLICATION_WITHOUT_APPROVAL",
    "MUTATE_FACTORY_WITHOUT_POLICY_DECISION",
    "CALL_LIVE_PROVIDER_WITHOUT_GATE",
    "CALL_EXTERNAL_SYSTEM_WITHOUT_GATE",
    "MERGE_WITHOUT_HUMAN_APPROVAL",
    "TAG_WITHOUT_HUMAN_APPROVAL",
    "RELEASE_WITHOUT_HUMAN_APPROVAL",
    "BYPASS_EVIDENCE_CAPTURE",
    "BYPASS_VALIDATION_GATES",
)

ACTIONS: tuple[AutonomyAction, ...] = (
    AutonomyAction("VIEW_FACTORY_STATUS", "evidence_packaging", "low", 1, "read_only", True, False, False, True, False, "Display factory status and dashboard metadata."),
    AutonomyAction("BUILD_REQUIREMENT_PREVIEW", "requirement_intake", "low", 1, "preview", True, False, False, True, False, "Normalize requirement intake into deterministic preview."),
    AutonomyAction("RUN_VALIDATORS", "governance_validation", "medium", 2, "local_validation", True, False, False, True, False, "Run allowlisted local validators."),
    AutonomyAction("RUN_TESTS", "sandbox_validation", "medium", 2, "local_validation", True, False, False, True, False, "Run local test suites under project validation gates."),
    AutonomyAction("GENERATE_IN_SANDBOX", "sandbox_generation", "medium", 3, "sandbox", True, False, False, True, True, "Generate application changes in sandbox only."),
    AutonomyAction("SELF_HEAL_LOW_RISK_IN_SANDBOX", "self_healing", "medium", 3, "sandbox", True, False, True, True, True, "Apply low-risk self-healing repairs in sandbox."),
    AutonomyAction("PROMOTE_SANDBOX_TO_WORKTREE", "worktree_promotion", "high", 4, "worktree", True, True, True, True, True, "Promote sandbox changes to worktree after human approval."),
    AutonomyAction("PREPARE_RELEASE_CANDIDATE", "release_candidate_preparation", "high", 5, "release_candidate", True, True, True, True, True, "Prepare release candidate evidence after validation."),
    AutonomyAction("CALL_LIVE_PROVIDER", "prompt_pack_generation", "high", 5, "live_provider", True, True, True, True, False, "Call live provider only behind provider gate and approval."),
    AutonomyAction("CALL_EXTERNAL_SYSTEM", "handover_replay", "high", 5, "external_system", True, True, True, True, False, "Call external system only behind external integration gate."),
    AutonomyAction("MERGE_MAIN", "merge_tag_release", "release", 5, "release_gate", True, True, True, True, True, "Merge to main only after human release approval."),
    AutonomyAction("TAG_RELEASE", "merge_tag_release", "release", 5, "release_gate", True, True, True, True, True, "Create tags only after human release approval."),
    AutonomyAction("ARBITRARY_SHELL_COMMAND", "planning", "prohibited", 99, "blocked", False, True, True, True, True, "Arbitrary shell command execution is blocked."),
    AutonomyAction("DELETE_REAL_GENERATED_APPLICATION", "worktree_promotion", "prohibited", 99, "blocked", False, True, True, True, True, "Deleting the real generated application is blocked."),
)


def action_catalog() -> dict[str, AutonomyAction]:
    return {action.action_id: action for action in ACTIONS}


def decide_autonomy_action(
    action_id: str,
    requested_autonomy_level: int,
    human_approved: bool = False,
    sandbox_evidence_present: bool = False,
    policy_evidence_present: bool = True,
) -> AutonomyDecision:
    actions = action_catalog()
    action = actions.get(action_id)
    if action is None:
        return AutonomyDecision(
            action_id=action_id,
            status=DecisionStatus.BLOCKED,
            requested_autonomy_level=requested_autonomy_level,
            reasons=("Unknown action.",),
            human_approval_required=True,
            evidence_required=("known_action_catalog_entry",),
            execution_zone="blocked",
            mutation_allowed_now=False,
            release_allowed_now=False,
            live_provider_call_allowed_now=False,
            external_system_call_allowed_now=False,
        )

    evidence_required: list[str] = []
    if action.policy_evidence_required:
        evidence_required.append("policy_evidence")
    if action.sandbox_evidence_required:
        evidence_required.append("sandbox_evidence")
    if action.rollback_required:
        evidence_required.append("rollback_plan")

    if not action.allowed:
        return AutonomyDecision(
            action_id=action_id,
            status=DecisionStatus.BLOCKED,
            requested_autonomy_level=requested_autonomy_level,
            reasons=(f"Action {action_id} is explicitly blocked.",),
            human_approval_required=True,
            evidence_required=tuple(evidence_required),
            execution_zone=action.execution_zone,
            mutation_allowed_now=False,
            release_allowed_now=False,
            live_provider_call_allowed_now=False,
            external_system_call_allowed_now=False,
        )

    if requested_autonomy_level < action.minimum_autonomy_level:
        return AutonomyDecision(
            action_id=action_id,
            status=DecisionStatus.BLOCKED,
            requested_autonomy_level=requested_autonomy_level,
            reasons=(f"Requested autonomy level {requested_autonomy_level} is below required level {action.minimum_autonomy_level}.",),
            human_approval_required=action.human_approval_required,
            evidence_required=tuple(evidence_required),
            execution_zone=action.execution_zone,
            mutation_allowed_now=False,
            release_allowed_now=False,
            live_provider_call_allowed_now=False,
            external_system_call_allowed_now=False,
        )

    if action.policy_evidence_required and not policy_evidence_present:
        return AutonomyDecision(
            action_id=action_id,
            status=DecisionStatus.POLICY_EVIDENCE_REQUIRED,
            requested_autonomy_level=requested_autonomy_level,
            reasons=("Policy evidence is required before this action.",),
            human_approval_required=action.human_approval_required,
            evidence_required=tuple(evidence_required),
            execution_zone=action.execution_zone,
            mutation_allowed_now=False,
            release_allowed_now=False,
            live_provider_call_allowed_now=False,
            external_system_call_allowed_now=False,
        )

    if action.sandbox_evidence_required and not sandbox_evidence_present:
        return AutonomyDecision(
            action_id=action_id,
            status=DecisionStatus.SANDBOX_EVIDENCE_REQUIRED,
            requested_autonomy_level=requested_autonomy_level,
            reasons=("Sandbox evidence is required before this action.",),
            human_approval_required=action.human_approval_required,
            evidence_required=tuple(evidence_required),
            execution_zone=action.execution_zone,
            mutation_allowed_now=False,
            release_allowed_now=False,
            live_provider_call_allowed_now=False,
            external_system_call_allowed_now=False,
        )

    if action.human_approval_required and not human_approved:
        return AutonomyDecision(
            action_id=action_id,
            status=DecisionStatus.HUMAN_APPROVAL_REQUIRED,
            requested_autonomy_level=requested_autonomy_level,
            reasons=("Human approval is required before this action.",),
            human_approval_required=True,
            evidence_required=tuple(evidence_required),
            execution_zone=action.execution_zone,
            mutation_allowed_now=False,
            release_allowed_now=False,
            live_provider_call_allowed_now=False,
            external_system_call_allowed_now=False,
        )

    release_allowed = action.execution_zone == "release_gate" and human_approved
    live_allowed = action.execution_zone == "live_provider" and human_approved
    external_allowed = action.execution_zone == "external_system" and human_approved
    mutation_allowed = action.execution_zone == "worktree" and human_approved

    return AutonomyDecision(
        action_id=action_id,
        status=DecisionStatus.APPROVED,
        requested_autonomy_level=requested_autonomy_level,
        reasons=("Action approved by governed autonomy control plane.",),
        human_approval_required=action.human_approval_required,
        evidence_required=tuple(evidence_required),
        execution_zone=action.execution_zone,
        mutation_allowed_now=mutation_allowed,
        release_allowed_now=release_allowed,
        live_provider_call_allowed_now=live_allowed,
        external_system_call_allowed_now=external_allowed,
    )


def build_governed_autonomy_control_plane(default_autonomy_level: int = 4) -> dict[str, object]:
    representative_decisions = [
        decide_autonomy_action("VIEW_FACTORY_STATUS", default_autonomy_level).to_dict(),
        decide_autonomy_action("GENERATE_IN_SANDBOX", default_autonomy_level).to_dict(),
        decide_autonomy_action("PROMOTE_SANDBOX_TO_WORKTREE", default_autonomy_level, sandbox_evidence_present=True).to_dict(),
        decide_autonomy_action("PROMOTE_SANDBOX_TO_WORKTREE", default_autonomy_level, human_approved=True, sandbox_evidence_present=True).to_dict(),
        decide_autonomy_action("MERGE_MAIN", default_autonomy_level, human_approved=True, sandbox_evidence_present=True).to_dict(),
        decide_autonomy_action("ARBITRARY_SHELL_COMMAND", default_autonomy_level).to_dict(),
    ]
    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_allowed": False,
        "auto_merge_allowed": False,
        "auto_release_allowed": False,
        "auto_tag_allowed": False,
        "autonomy_levels": list(AUTONOMY_LEVELS),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "control_plane_only": True,
        "default_autonomy_level": default_autonomy_level,
        "external_system_calls_allowed_by_default": False,
        "factory_self_modification_allowed_without_approval": False,
        "lifecycle_activities": list(LIFECYCLE_ACTIVITIES),
        "live_provider_calls_allowed_by_default": False,
        "real_generated_application_delete_allowed": False,
        "real_generated_application_overwrite_allowed_without_approval": False,
        "release_gates_require_human_approval": True,
        "representative_decisions": representative_decisions,
        "risk_tiered_action_catalog": [action.to_dict() for action in ACTIONS],
        "schema_version": "governed-autonomy-control-plane.v1",
        "status": READY,
        "worktree_mutation_requires_human_approval": True,
    }


def validate_governed_autonomy_control_plane(control_plane: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if control_plane.get("schema_version") != "governed-autonomy-control-plane.v1":
        failures.append("Invalid control plane schema")
    if control_plane.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if control_plane.get("status") != READY:
        failures.append("Control plane must be ready")
    for key in [
        "arbitrary_shell_execution_allowed",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
        "external_system_calls_allowed_by_default",
        "live_provider_calls_allowed_by_default",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed_without_approval",
        "factory_self_modification_allowed_without_approval",
    ]:
        if control_plane.get(key) is not False:
            failures.append(f"{key} must be false")
    for key in [
        "control_plane_only",
        "release_gates_require_human_approval",
        "worktree_mutation_requires_human_approval",
    ]:
        if control_plane.get(key) is not True:
            failures.append(f"{key} must be true")
    catalog = control_plane.get("risk_tiered_action_catalog")
    if not isinstance(catalog, list) or len(catalog) < 10:
        failures.append("Risk-tiered action catalog must include required action coverage")
    blocked = control_plane.get("blocked_actions")
    if not isinstance(blocked, list):
        failures.append("Blocked action catalog must be present")
    else:
        for action in BLOCKED_ACTIONS:
            if action not in blocked:
                failures.append(f"Missing blocked action: {action}")
    activities = control_plane.get("lifecycle_activities")
    if not isinstance(activities, list):
        failures.append("Lifecycle activities must be listed")
    else:
        for activity in LIFECYCLE_ACTIVITIES:
            if activity not in activities:
                failures.append(f"Missing lifecycle activity: {activity}")
    return failures


def write_governed_autonomy_control_plane(control_plane: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(control_plane, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governed A-to-Z autonomy control plane.")
    parser.add_argument("--default-autonomy-level", type=int, default=4)
    parser.add_argument("--audit-out", type=Path)
    parser.add_argument("--decide-action")
    parser.add_argument("--human-approved", action="store_true")
    parser.add_argument("--sandbox-evidence-present", action="store_true")
    parser.add_argument("--policy-evidence-present", action="store_true", default=True)
    args = parser.parse_args()

    if args.decide_action:
        decision = decide_autonomy_action(
            action_id=args.decide_action,
            requested_autonomy_level=args.default_autonomy_level,
            human_approved=args.human_approved,
            sandbox_evidence_present=args.sandbox_evidence_present,
            policy_evidence_present=args.policy_evidence_present,
        )
        print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
        return 0 if decision.status == DecisionStatus.APPROVED else 2

    control_plane = build_governed_autonomy_control_plane(args.default_autonomy_level)
    if args.audit_out is not None:
        write_governed_autonomy_control_plane(control_plane, args.audit_out)
    print(json.dumps(control_plane, indent=2, sort_keys=True))
    failures = validate_governed_autonomy_control_plane(control_plane)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
