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

from scripts.build_governed_autonomous_self_engineering_orchestrator import (
    READY as PHASE14J_READY,
    build_governed_autonomous_self_engineering_orchestrator,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


APP_ID = "upi_dispute_resolution"
READY = "GOVERNED_AUTONOMOUS_PHASE_EXECUTION_LOOP_READY"

EXECUTION_LOOP_STAGES: tuple[str, ...] = (
    "load_orchestrator_boundary",
    "select_candidate_phase",
    "generate_candidate_phase_plan",
    "generate_candidate_artifact_manifest",
    "run_validation_gate_plan",
    "classify_failures",
    "apply_allowed_low_risk_repairs",
    "rerun_validation_gate_plan",
    "emit_execution_evidence",
    "stop_at_human_approval_gate",
)

CANDIDATE_NEXT_PHASES: tuple[str, ...] = (
    "14L_OPERATOR_PORTAL_AUTONOMOUS_CERTIFICATION_DASHBOARD_INTEGRATION",
    "14M_GENERATED_APPLICATION_MATURITY_SWEEP",
    "14N_V1_RELEASE_CANDIDATE_REPLAY_GATE",
)

VALIDATION_GATES: tuple[str, ...] = (
    "phase_policy_validator",
    "targeted_phase_tests",
    "self_healing_adoption_gate",
    "ruff",
    "mypy",
    "full_pytest",
)

HUMAN_GATED_ACTIONS: tuple[str, ...] = (
    "promotion",
    "merge_to_main",
    "tag_creation",
    "release_declaration",
    "destructive_generated_application_mutation",
    "live_provider_calls",
    "external_system_calls",
    "official_certification_claims",
    "official_certification_decisions",
)


@dataclass(frozen=True)
class ExecutionStage:
    stage_id: str
    execution_mode: str
    human_gate_required: bool
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_mode": self.execution_mode,
            "human_gate_required": self.human_gate_required,
            "stage_id": self.stage_id,
            "summary": self.summary,
        }


def build_execution_stages() -> tuple[ExecutionStage, ...]:
    return (
        ExecutionStage("load_orchestrator_boundary", "AUTONOMOUS_READ_ONLY", False, "Load Phase 14J orchestrator controls."),
        ExecutionStage("select_candidate_phase", "AUTONOMOUS_PLANNING", False, "Select the next approved candidate phase."),
        ExecutionStage("generate_candidate_phase_plan", "AUTONOMOUS_PLANNING", False, "Generate the phase plan and expected artifacts."),
        ExecutionStage("generate_candidate_artifact_manifest", "AUTONOMOUS_SELF_ENGINEERING", False, "Plan docs, policies, scripts, tests, and evidence artifacts."),
        ExecutionStage("run_validation_gate_plan", "AUTONOMOUS_VALIDATION", False, "Run planned validators and quality gates."),
        ExecutionStage("classify_failures", "AUTONOMOUS_DIAGNOSIS", False, "Classify failures into low-risk repairable or human-gated."),
        ExecutionStage("apply_allowed_low_risk_repairs", "GOVERNED_LOW_RISK_SELF_HEALING", False, "Apply only policy-approved low-risk repairs."),
        ExecutionStage("rerun_validation_gate_plan", "AUTONOMOUS_VALIDATION", False, "Rerun gates after repairs."),
        ExecutionStage("emit_execution_evidence", "AUTONOMOUS_EVIDENCE_CAPTURE", False, "Emit deterministic execution evidence."),
        ExecutionStage("stop_at_human_approval_gate", "HUMAN_GATE_REQUIRED", True, "Stop before merge, tag, release, promotion, live calls, or certification claims."),
    )


def build_governed_autonomous_phase_execution_loop(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    selected_candidate_phase: str = CANDIDATE_NEXT_PHASES[0],
) -> dict[str, object]:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator(
        requirement_id=requirement_id
    )

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "autonomous_execution_allowed_inside_governed_branch": True,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "candidate_next_phases": list(CANDIDATE_NEXT_PHASES),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "execution_loop_stages": [stage.to_dict() for stage in build_execution_stages()],
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_tag": True,
        "human_gated_actions": list(HUMAN_GATED_ACTIONS),
        "live_provider_calls_performed": False,
        "low_risk_self_healing_allowed": True,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "governed-autonomous-phase-execution-loop.v1",
        "selected_candidate_phase": selected_candidate_phase,
        "self_evolution_allowed_for_docs_policies_tests_evidence": True,
        "status": READY,
        "supporting_orchestrator_expected_status": PHASE14J_READY,
        "supporting_orchestrator_status": orchestrator["status"],
        "validation_gates": list(VALIDATION_GATES),
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_governed_autonomous_phase_execution_loop(loop: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if loop.get("schema_version") != "governed-autonomous-phase-execution-loop.v1":
        failures.append("Invalid governed autonomous phase execution loop schema")
    if loop.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if loop.get("status") != READY:
        failures.append("Execution loop must be ready")

    for key in [
        "autonomous_execution_allowed_inside_governed_branch",
        "low_risk_self_healing_allowed",
        "self_evolution_allowed_for_docs_policies_tests_evidence",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
    ]:
        if loop.get(key) is not True:
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
        if loop.get(key) is not False:
            failures.append(f"{key} must be false")

    selected = loop.get("selected_candidate_phase")
    if selected not in CANDIDATE_NEXT_PHASES:
        failures.append("Selected candidate phase must be policy-approved")

    stages_value = loop.get("execution_loop_stages")
    if not isinstance(stages_value, list):
        failures.append("Execution loop stages must be listed")
    else:
        stage_ids: set[str] = set()
        human_gate_found = False
        for stage in stages_value:
            if isinstance(stage, dict):
                stage_id = stage.get("stage_id")
                if isinstance(stage_id, str):
                    stage_ids.add(stage_id)
                if stage.get("human_gate_required") is True:
                    human_gate_found = True
        for stage_id in EXECUTION_LOOP_STAGES:
            if stage_id not in stage_ids:
                failures.append(f"Missing execution loop stage: {stage_id}")
        if not human_gate_found:
            failures.append("At least one execution stage must require human gate")

    gates_value = loop.get("validation_gates")
    if not isinstance(gates_value, list):
        failures.append("Validation gates must be listed")
    else:
        gate_names = {str(item) for item in gates_value}
        for gate in VALIDATION_GATES:
            if gate not in gate_names:
                failures.append(f"Missing validation gate: {gate}")

    gated_value = loop.get("human_gated_actions")
    if not isinstance(gated_value, list):
        failures.append("Human-gated actions must be listed")
    else:
        gated_names = {str(item) for item in gated_value}
        for action in HUMAN_GATED_ACTIONS:
            if action not in gated_names:
                failures.append(f"Missing human-gated action: {action}")

    boundary_value = loop.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if loop.get("supporting_orchestrator_status") != PHASE14J_READY:
        failures.append("Supporting Phase 14J orchestrator must be ready")
    return failures


def write_execution_loop(loop: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(loop, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governed autonomous phase execution loop.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--selected-candidate-phase", default=CANDIDATE_NEXT_PHASES[0])
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    loop = build_governed_autonomous_phase_execution_loop(
        requirement_id=args.requirement_id,
        selected_candidate_phase=args.selected_candidate_phase,
    )
    if args.audit_out is not None:
        write_execution_loop(loop, args.audit_out)
    print(json.dumps(loop, indent=2, sort_keys=True))
    failures = validate_governed_autonomous_phase_execution_loop(loop)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
