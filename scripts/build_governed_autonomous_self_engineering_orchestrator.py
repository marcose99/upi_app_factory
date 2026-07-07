#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_certification_readiness_dashboard_index import (
    READY as PHASE14I_READY,
    build_certification_readiness_dashboard_index,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


APP_ID = "upi_dispute_resolution"
READY = "GOVERNED_AUTONOMOUS_SELF_ENGINEERING_ORCHESTRATOR_READY"

ALLOWED_AUTONOMOUS_ACTIONS: tuple[str, ...] = (
    "read_phase_state",
    "plan_next_phase",
    "write_candidate_artifacts",
    "run_policy_validators",
    "run_targeted_tests",
    "run_ruff",
    "run_mypy",
    "run_full_pytest",
    "diagnose_failures",
    "apply_policy_allowed_low_risk_repairs",
    "rerun_gates",
    "emit_evidence",
    "stop_at_human_approval_gate",
)

BLOCKED_ACTIONS: tuple[str, ...] = (
    "merge_to_main_without_human_approval",
    "create_tag_without_human_approval",
    "release_without_human_approval",
    "claim_official_certification",
    "grant_certification",
    "delete_real_generated_application",
    "overwrite_real_generated_application_without_approval",
    "execute_arbitrary_shell",
    "call_live_provider",
    "call_external_system",
    "bypass_evidence_capture",
    "bypass_validation_gates",
)

ORCHESTRATION_STEPS: tuple[str, ...] = (
    "discover_current_phase_state",
    "select_next_governed_phase",
    "build_candidate_change_plan",
    "write_candidate_docs_policies_scripts_tests",
    "run_deterministic_validation_gates",
    "diagnose_validation_failures",
    "apply_allowed_low_risk_repairs",
    "rerun_validation_gates",
    "emit_governed_evidence",
    "stop_before_human_gated_actions",
)


@dataclass(frozen=True)
class OrchestrationStep:
    step_id: str
    autonomy_mode: str
    human_gate_required: bool
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "autonomy_mode": self.autonomy_mode,
            "human_gate_required": self.human_gate_required,
            "step_id": self.step_id,
            "summary": self.summary,
        }


def build_orchestration_steps() -> tuple[OrchestrationStep, ...]:
    return (
        OrchestrationStep(
            "discover_current_phase_state",
            "AUTONOMOUS_READ_ONLY",
            False,
            "Read current branch, tags, phase artifacts, validators, and dashboard index.",
        ),
        OrchestrationStep(
            "select_next_governed_phase",
            "AUTONOMOUS_PLANNING",
            False,
            "Choose the next bounded phase from policy-approved roadmap candidates.",
        ),
        OrchestrationStep(
            "build_candidate_change_plan",
            "AUTONOMOUS_PLANNING",
            False,
            "Create a deterministic candidate plan with files, tests, and evidence outputs.",
        ),
        OrchestrationStep(
            "write_candidate_docs_policies_scripts_tests",
            "AUTONOMOUS_SELF_ENGINEERING",
            False,
            "Write candidate artifacts inside the active work branch only.",
        ),
        OrchestrationStep(
            "run_deterministic_validation_gates",
            "AUTONOMOUS_VALIDATION",
            False,
            "Run validators, targeted tests, Ruff, MyPy, and full pytest.",
        ),
        OrchestrationStep(
            "diagnose_validation_failures",
            "AUTONOMOUS_DIAGNOSIS",
            False,
            "Classify validation failures and decide whether repair is low-risk.",
        ),
        OrchestrationStep(
            "apply_allowed_low_risk_repairs",
            "GOVERNED_LOW_RISK_SELF_HEALING",
            False,
            "Apply only policy-approved repairs that do not bypass evidence or gates.",
        ),
        OrchestrationStep(
            "rerun_validation_gates",
            "AUTONOMOUS_VALIDATION",
            False,
            "Rerun deterministic gates after repairs.",
        ),
        OrchestrationStep(
            "emit_governed_evidence",
            "AUTONOMOUS_EVIDENCE_CAPTURE",
            False,
            "Emit audit, decision, validation, and self-healing evidence.",
        ),
        OrchestrationStep(
            "stop_before_human_gated_actions",
            "HUMAN_GATE_REQUIRED",
            True,
            "Stop before merge, tag, release, promotion, live calls, or certification claims.",
        ),
    )


def build_governed_autonomous_self_engineering_orchestrator(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    dashboard_index = build_certification_readiness_dashboard_index(requirement_id=requirement_id)

    return {
        "allowed_autonomous_actions": list(ALLOWED_AUTONOMOUS_ACTIONS),
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "blocked_actions": list(BLOCKED_ACTIONS),
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "governed_autonomous_self_engineering_allowed": True,
        "governed_low_risk_self_healing_allowed": True,
        "governed_self_evolution_allowed": True,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_tag": True,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "orchestration_steps": [step.to_dict() for step in build_orchestration_steps()],
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "governed-autonomous-self-engineering-orchestrator.v1",
        "status": READY,
        "supporting_dashboard_index_expected_status": PHASE14I_READY,
        "supporting_dashboard_index_status": dashboard_index["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_governed_autonomous_self_engineering_orchestrator(
    orchestrator: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    if orchestrator.get("schema_version") != "governed-autonomous-self-engineering-orchestrator.v1":
        failures.append("Invalid governed autonomous self-engineering schema")
    if orchestrator.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if orchestrator.get("status") != READY:
        failures.append("Orchestrator must be ready")

    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "governed_autonomous_self_engineering_allowed",
        "governed_low_risk_self_healing_allowed",
        "governed_self_evolution_allowed",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]:
        if orchestrator.get(key) is not True:
            failures.append(f"{key} must be true")

    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_without_policy_performed",
        "live_provider_calls_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_performed",
    ]:
        if orchestrator.get(key) is not False:
            failures.append(f"{key} must be false")

    actions_value = orchestrator.get("allowed_autonomous_actions")
    if not isinstance(actions_value, list):
        failures.append("Allowed autonomous actions must be listed")
    else:
        action_names = {str(item) for item in actions_value}
        for action in ALLOWED_AUTONOMOUS_ACTIONS:
            if action not in action_names:
                failures.append(f"Missing allowed action: {action}")

    blocked_value = orchestrator.get("blocked_actions")
    if not isinstance(blocked_value, list):
        failures.append("Blocked actions must be listed")
    else:
        blocked_names = {str(item) for item in blocked_value}
        for action in BLOCKED_ACTIONS:
            if action not in blocked_names:
                failures.append(f"Missing blocked action: {action}")

    steps_value = orchestrator.get("orchestration_steps")
    if not isinstance(steps_value, list):
        failures.append("Orchestration steps must be listed")
    else:
        step_ids: set[str] = set()
        human_gate_found = False
        for step in steps_value:
            if isinstance(step, dict):
                step_id = step.get("step_id")
                if isinstance(step_id, str):
                    step_ids.add(step_id)
                if step.get("human_gate_required") is True:
                    human_gate_found = True
        for step_id in ORCHESTRATION_STEPS:
            if step_id not in step_ids:
                failures.append(f"Missing orchestration step: {step_id}")
        if not human_gate_found:
            failures.append("At least one orchestration step must require a human gate")

    boundary_value = orchestrator.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if orchestrator.get("supporting_dashboard_index_status") != PHASE14I_READY:
        failures.append("Supporting Phase 14I dashboard index must be ready")
    return failures


def write_orchestrator(orchestrator: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(orchestrator, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governed autonomous self-engineering orchestrator.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    orchestrator = build_governed_autonomous_self_engineering_orchestrator(
        requirement_id=args.requirement_id
    )
    if args.audit_out is not None:
        write_orchestrator(orchestrator, args.audit_out)
    print(json.dumps(orchestrator, indent=2, sort_keys=True))
    failures = validate_governed_autonomous_self_engineering_orchestrator(orchestrator)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
