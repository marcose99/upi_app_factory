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

from scripts.build_generated_application_maturity_sweep import (
    READY as PHASE14M_READY,
    build_generated_application_maturity_sweep,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_certification_dashboard_integration import (
    READY as PHASE14L_READY,
    build_operator_portal_certification_dashboard_integration,
)
from scripts.run_governed_autonomous_phase_execution_loop import (
    READY as PHASE14K_READY,
    build_governed_autonomous_phase_execution_loop,
)


APP_ID = "upi_dispute_resolution"
READY = "V1_RELEASE_CANDIDATE_REPLAY_GATE_READY"

REPLAY_GATE_STEPS: tuple[str, ...] = (
    "fresh_clone_or_clean_checkout",
    "python_310_environment_check",
    "dependency_installation_check",
    "factory_validation_gates",
    "generated_application_tests",
    "operator_portal_start_check",
    "certification_readiness_dashboard_check",
    "evidence_artifact_inventory_check",
    "handover_runbook_check",
    "human_release_candidate_approval_gate",
)

EVIDENCE_ARTIFACTS: tuple[str, ...] = (
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14d/certification_ready_release_candidate_evidence_audit.json",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14e/fresh_recipient_certification_evidence_replay_audit.json",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14l/operator_portal_certification_dashboard_audit.json",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14m/generated_application_maturity_sweep_audit.json",
)


@dataclass(frozen=True)
class ReplayGateStep:
    step_id: str
    status: str
    evidence: str
    human_gate_required: bool
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence": self.evidence,
            "human_gate_required": self.human_gate_required,
            "status": self.status,
            "step_id": self.step_id,
            "summary": self.summary,
        }


def _exists(path_text: str) -> bool:
    return Path(path_text).exists()


def build_replay_gate_steps() -> tuple[ReplayGateStep, ...]:
    return (
        ReplayGateStep("fresh_clone_or_clean_checkout", "READY_FOR_REPLAY", "git clone / clean checkout runbook", False, "Recipient starts from a clean checkout."),
        ReplayGateStep("python_310_environment_check", "READY_FOR_REPLAY", "Python 3.10.12 gate", False, "Replay requires Python 3.10.x."),
        ReplayGateStep("dependency_installation_check", "READY_FOR_REPLAY", "project dependency install command", False, "Dependencies must install locally."),
        ReplayGateStep("factory_validation_gates", "READY_FOR_REPLAY", "pytest, Ruff, MyPy, validators", False, "Factory validation gates must pass."),
        ReplayGateStep("generated_application_tests", "READY_FOR_REPLAY", "generated_application/tests", False, "Generated application tests must pass locally."),
        ReplayGateStep("operator_portal_start_check", "READY_FOR_REPLAY", "scripts/start_factory_operator_portal.py", False, "Operator portal must start locally."),
        ReplayGateStep("certification_readiness_dashboard_check", "READY_FOR_REPLAY", "Phase 14L dashboard integration", False, "Operator can inspect certification readiness."),
        ReplayGateStep("evidence_artifact_inventory_check", "READY_FOR_REPLAY", "phase14d_to_phase14m_artifacts", False, "Evidence inventory must be present."),
        ReplayGateStep("handover_runbook_check", "READY_FOR_REPLAY", "handover docs and replay scripts", False, "Recipient handover instructions must be available."),
        ReplayGateStep("human_release_candidate_approval_gate", "HUMAN_APPROVAL_REQUIRED", "human approval record", True, "Human approval is required before RC declaration."),
    )


def build_v1_release_candidate_replay_gate(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    execution_loop = build_governed_autonomous_phase_execution_loop(requirement_id=requirement_id)
    portal_dashboard = build_operator_portal_certification_dashboard_integration(
        requirement_id=requirement_id
    )
    maturity_sweep = build_generated_application_maturity_sweep(requirement_id=requirement_id)

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "evidence_artifacts": list(EVIDENCE_ARTIFACTS),
        "evidence_artifacts_exist": all(_exists(path) for path in EVIDENCE_ARTIFACTS),
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_release_candidate_declaration": True,
        "human_approval_required_for_tag": True,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "release_candidate_gate_only": True,
        "release_execution_performed": False,
        "replay_gate_steps": [step.to_dict() for step in build_replay_gate_steps()],
        "requirement_id": requirement_id,
        "schema_version": "v1-release-candidate-replay-gate.v1",
        "status": READY,
        "supporting_execution_loop_expected_status": PHASE14K_READY,
        "supporting_execution_loop_status": execution_loop["status"],
        "supporting_generated_application_maturity_expected_status": PHASE14M_READY,
        "supporting_generated_application_maturity_status": maturity_sweep["status"],
        "supporting_portal_dashboard_expected_status": PHASE14L_READY,
        "supporting_portal_dashboard_status": portal_dashboard["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_v1_release_candidate_replay_gate(gate: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if gate.get("schema_version") != "v1-release-candidate-replay-gate.v1":
        failures.append("Invalid v1 release-candidate replay gate schema")
    if gate.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if gate.get("status") != READY:
        failures.append("v1 release-candidate replay gate must be ready")

    for key in [
        "release_candidate_gate_only",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_release_candidate_declaration",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]:
        if gate.get(key) is not True:
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
        if gate.get(key) is not False:
            failures.append(f"{key} must be false")

    if gate.get("evidence_artifacts_exist") is not True:
        failures.append("Required evidence artifacts must exist")

    steps_value = gate.get("replay_gate_steps")
    if not isinstance(steps_value, list):
        failures.append("Replay gate steps must be listed")
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
        for step_id in REPLAY_GATE_STEPS:
            if step_id not in step_ids:
                failures.append(f"Missing replay gate step: {step_id}")
        if not human_gate_found:
            failures.append("Release-candidate replay gate must include a human approval step")

    boundary_value = gate.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if gate.get("supporting_execution_loop_status") != PHASE14K_READY:
        failures.append("Supporting Phase 14K execution loop must be ready")
    if gate.get("supporting_portal_dashboard_status") != PHASE14L_READY:
        failures.append("Supporting Phase 14L portal dashboard must be ready")
    if gate.get("supporting_generated_application_maturity_status") != PHASE14M_READY:
        failures.append("Supporting Phase 14M maturity sweep must be ready")
    return failures


def write_replay_gate(gate: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v1.0 release-candidate replay gate.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    gate = build_v1_release_candidate_replay_gate(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_replay_gate(gate, args.audit_out)
    print(json.dumps(gate, indent=2, sort_keys=True))
    failures = validate_v1_release_candidate_replay_gate(gate)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
