#!/usr/bin/env python3
"""Autonomous standards-gap phase engineering runner.

Phase 13AT is planning-only. It turns planned standards controls into future
phase blueprints, but does not apply repairs, self-modify the repository,
merge, tag, release, call live providers, or call external systems.
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


from scripts.build_local_industry_standards_control_matrix import (  # noqa: E402
    READY as MATRIX_READY,
    STATUS_PLANNED,
    StandardsControl,
    build_local_standards_control_matrix,
)


APP_ID = "upi_dispute_resolution"
READY = "AUTONOMOUS_PHASE_BLUEPRINTS_READY"
BLOCKED = "AUTONOMOUS_PHASE_BLUEPRINTS_BLOCKED_BY_STANDARDS_MATRIX"

BLUEPRINT_ITEMS: tuple[str, ...] = (
    "source_standard_control",
    "future_phase_id",
    "artifact_plan",
    "validator_plan",
    "test_plan",
    "evidence_plan",
    "self_healing_linkage",
    "risk_tier",
    "human_approval_boundary",
    "blocked_actions",
)


@dataclass(frozen=True)
class PhaseBlueprint:
    """One autonomous future phase blueprint."""

    future_phase_id: str
    source_control_id: str
    standard_family: str
    title: str
    risk_tier: str
    branch_name: str
    artifact_plan: tuple[str, ...]
    validator_plan: tuple[str, ...]
    test_plan: tuple[str, ...]
    evidence_plan: tuple[str, ...]
    self_healing_linkage: str
    human_approval_boundary: str
    blocked_actions: tuple[str, ...]
    auto_apply_allowed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_plan": list(self.artifact_plan),
            "auto_apply_allowed": self.auto_apply_allowed,
            "blocked_actions": list(self.blocked_actions),
            "branch_name": self.branch_name,
            "evidence_plan": list(self.evidence_plan),
            "future_phase_id": self.future_phase_id,
            "human_approval_boundary": self.human_approval_boundary,
            "risk_tier": self.risk_tier,
            "self_healing_linkage": self.self_healing_linkage,
            "source_control_id": self.source_control_id,
            "standard_family": self.standard_family,
            "test_plan": list(self.test_plan),
            "title": self.title,
            "validator_plan": list(self.validator_plan),
        }


@dataclass(frozen=True)
class AutonomousPhaseEngineeringRun:
    """Autonomous standards-gap phase engineering run."""

    app_id: str
    runner_status: str
    preferred_term: str
    project_root: str
    standards_matrix_ready: bool
    blueprint_digest: str
    blueprints: tuple[PhaseBlueprint, ...]
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    destructive_execution_performed: bool
    factory_self_healing_repair_applied: bool
    factory_self_modification_applied: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.runner_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "blueprint_digest": self.blueprint_digest,
            "blueprints": [blueprint.to_dict() for blueprint in self.blueprints],
            "destructive_execution_performed": self.destructive_execution_performed,
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_healing_repair_applied": self.factory_self_healing_repair_applied,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "runner_status": self.runner_status,
            "schema_version": "autonomous-phase-engineering-run.v1",
            "standards_matrix_ready": self.standards_matrix_ready,
        }


def _slug(value: str) -> str:
    return value.lower().replace("_", "-").replace(" ", "-")


def _risk_tier(control: StandardsControl) -> str:
    if control.standard_family in {"SLSA_PROVENANCE", "CYCLONEDX_SBOM", "PAYMENT_COMPLIANCE_TRACEABILITY"}:
        return "medium"
    if control.standard_family in {"NIST_AI_RMF", "OWASP_LLM_TOP_10"}:
        return "high"
    return "low"


def _future_phase_id(index: int) -> str:
    phase_number = 13
    letter_offset = ord("U") + index
    return f"{phase_number}{chr(letter_offset)}"


def _build_blueprint(control: StandardsControl, index: int) -> PhaseBlueprint:
    phase_id = _future_phase_id(index)
    slug = _slug(control.standard_family)
    risk_tier = _risk_tier(control)
    blocked_actions = (
        "delete_real_generated_application",
        "overwrite_real_generated_application",
        "apply_factory_self_healing_repair",
        "apply_factory_self_modification",
        "call_live_llm_provider",
        "call_external_system",
        "auto_merge",
        "auto_tag",
        "auto_release",
    )

    return PhaseBlueprint(
        future_phase_id=phase_id,
        source_control_id=control.control_id,
        standard_family=control.standard_family,
        title=f"Implement local controls for {control.title}",
        risk_tier=risk_tier,
        branch_name=f"phase{phase_id.lower()}/{slug}-local-control",
        artifact_plan=(
            f"policies/phase{phase_id.lower()}_{slug}_policy.json",
            f"docs/phase{phase_id.lower()}/{slug}_local_control.md",
            f"scripts/build_{slug.replace('-', '_')}_evidence.py",
            f"scripts/validate_phase{phase_id.lower()}_{slug.replace('-', '_')}.py",
            f"tests/test_phase{phase_id.lower()}_{slug.replace('-', '_')}.py",
        ),
        validator_plan=(
            "policy schema validation",
            "control evidence validation",
            "blocked action validation",
            "local replay command validation",
        ),
        test_plan=(
            "blocked without dependencies",
            "ready with local evidence",
            "no live provider calls",
            "no external system calls",
            "no repair auto-apply",
            "no merge/tag/release",
        ),
        evidence_plan=(
            f"workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase{phase_id.lower()}/{slug}_audit.json",
            "deterministic JSON digest",
            "local replay command output",
        ),
        self_healing_linkage=control.self_healing_linkage,
        human_approval_boundary="Human approval is required for repair application, self-modification, merge, tag, release, live calls, and destructive actions.",
        blocked_actions=blocked_actions,
        auto_apply_allowed=False,
    )


def _digest_blueprints(blueprints: tuple[PhaseBlueprint, ...]) -> str:
    payload = [blueprint.to_dict() for blueprint in blueprints]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_autonomous_phase_engineering_run(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> AutonomousPhaseEngineeringRun:
    """Build an autonomous phase engineering run plan."""

    root = project_root.resolve()
    matrix = build_local_standards_control_matrix(
        project_root=root,
        approval_token=approval_token,
        operator_confirmation=operator_confirmation,
    )
    matrix_ready = matrix.matrix_status == MATRIX_READY
    planned_controls = tuple(
        control for control in matrix.controls if control.local_status == STATUS_PLANNED
    )
    blueprints = tuple(
        _build_blueprint(control, index) for index, control in enumerate(planned_controls)
    )
    status = READY if matrix_ready and blueprints else BLOCKED

    reasons = list(matrix.reasons)
    if status == READY:
        reasons.append("Autonomous phase blueprints are ready for human-reviewed standards-gap engineering.")
    else:
        reasons.append("Autonomous phase blueprints are blocked until the standards matrix is ready.")

    return AutonomousPhaseEngineeringRun(
        app_id=APP_ID,
        runner_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        standards_matrix_ready=matrix_ready,
        blueprint_digest=_digest_blueprints(blueprints),
        blueprints=blueprints,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        destructive_execution_performed=False,
        factory_self_healing_repair_applied=False,
        factory_self_modification_applied=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=tuple(reasons),
    )


def validate_autonomous_phase_engineering_run(
    run: AutonomousPhaseEngineeringRun,
) -> list[str]:
    """Validate autonomous phase engineering run safety and completeness."""

    failures: list[str] = []
    if run.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if run.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if run.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if run.destructive_execution_performed:
        failures.append("Phase 13AT must not perform destructive execution")
    if run.factory_self_healing_repair_applied:
        failures.append("Phase 13AT must not apply self-healing repairs")
    if run.factory_self_modification_applied:
        failures.append("Phase 13AT must not apply factory self-modification")
    if run.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if run.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if run.auto_merge_performed or run.auto_tag_performed or run.auto_release_performed:
        failures.append("Phase 13AT must not merge, tag, or release")
    if len(run.blueprint_digest) != 64:
        failures.append("Blueprint digest must be SHA-256 hex")
    if not run.blueprints:
        failures.append("At least one autonomous phase blueprint is required")
    for blueprint in run.blueprints:
        if blueprint.auto_apply_allowed:
            failures.append(f"{blueprint.future_phase_id} must not auto-apply")
        if not blueprint.self_healing_linkage.startswith("REPAIR-"):
            failures.append(f"{blueprint.future_phase_id} missing repair catalog linkage")
        if not blueprint.artifact_plan:
            failures.append(f"{blueprint.future_phase_id} missing artifact plan")
        if not blueprint.validator_plan:
            failures.append(f"{blueprint.future_phase_id} missing validator plan")
        if not blueprint.test_plan:
            failures.append(f"{blueprint.future_phase_id} missing test plan")
        if not blueprint.evidence_plan:
            failures.append(f"{blueprint.future_phase_id} missing evidence plan")
        if "auto_merge" not in blueprint.blocked_actions:
            failures.append(f"{blueprint.future_phase_id} must block auto_merge")
        if blueprint.risk_tier not in {"low", "medium", "high"}:
            failures.append(f"{blueprint.future_phase_id} has invalid risk tier")
    return failures


def write_autonomous_phase_engineering_run(
    run: AutonomousPhaseEngineeringRun,
    audit_out: Path,
) -> None:
    """Write deterministic JSON audit for autonomous phase engineering run."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(run.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run autonomous standards-gap phase engineering planner.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    run = build_autonomous_phase_engineering_run(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_autonomous_phase_engineering_run(run, args.audit_out)

    print(json.dumps(run.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_autonomous_phase_engineering_run(run)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if run.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
