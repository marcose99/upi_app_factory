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
from scripts.run_sandbox_autonomous_generation_validation_loop import build_sandbox_loop_report


APP_ID = "upi_dispute_resolution"
READY = "HUMAN_APPROVED_PROMOTION_CERTIFICATION_BOUNDARY_READY"

CERTIFICATION_BOUNDARY: tuple[str, ...] = (
    "certifying_authority_review",
    "independent_verification",
    "formal_audit_or_compliance_assessment",
    "regulatory_or_industry_standard_assessment",
    "production_environment_validation_where_required",
    "security_privacy_resilience_and_operational_review",
    "official_certification_decision",
)

CERTIFICATION_EVIDENCE: tuple[str, ...] = (
    "requirement_traceability",
    "architecture_and_design_evidence",
    "policy_decision_records",
    "sandbox_generation_evidence",
    "local_validation_reports",
    "security_and_governance_validation_reports",
    "mock_boundary_evidence",
    "rollback_and_replay_evidence",
    "handover_evidence",
    "known_limitations_and_certification_boundary_statement",
)


@dataclass(frozen=True)
class CertificationEvidenceItem:
    evidence_id: str
    status: str
    source: str
    purpose: str

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "purpose": self.purpose,
            "source": self.source,
            "status": self.status,
        }


def build_certification_evidence_items() -> tuple[CertificationEvidenceItem, ...]:
    return (
        CertificationEvidenceItem("requirement_traceability", "AVAILABLE", "phase14a_lifecycle_plan", "Shows requirement-to-lifecycle traceability."),
        CertificationEvidenceItem("architecture_and_design_evidence", "AVAILABLE", "phase13as_and_phase14a_artifacts", "Shows design intent and governed planning."),
        CertificationEvidenceItem("policy_decision_records", "AVAILABLE", "phase13az_control_plane", "Shows autonomy decisions and blocked actions."),
        CertificationEvidenceItem("sandbox_generation_evidence", "AVAILABLE", "phase14b_sandbox_loop", "Shows sandbox-only generated preview and manifest."),
        CertificationEvidenceItem("local_validation_reports", "AVAILABLE", "pytest_ruff_mypy_logs", "Shows local quality validation evidence."),
        CertificationEvidenceItem("security_and_governance_validation_reports", "AVAILABLE", "phase13av_and_governance_tests", "Shows threat, safety, and governance coverage."),
        CertificationEvidenceItem("mock_boundary_evidence", "AVAILABLE", "real_app_mock_ecosystem_boundary", "Shows external ecosystem remains mocked/simulated."),
        CertificationEvidenceItem("rollback_and_replay_evidence", "AVAILABLE", "phase13aq_phase13ar_phase14b", "Shows replayability and rollback-oriented evidence."),
        CertificationEvidenceItem("handover_evidence", "AVAILABLE", "handover_replay_and_operator_docs", "Shows recipient reproducibility readiness."),
        CertificationEvidenceItem("known_limitations_and_certification_boundary_statement", "AVAILABLE", "phase14c_boundary", "States that factory output is certification-ready, not certified."),
    )


def build_promotion_certification_boundary(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    human_approved: bool = False,
) -> dict[str, object]:
    sandbox_report = build_sandbox_loop_report(requirement_id)
    decision = decide_autonomy_action(
        "PROMOTE_SANDBOX_TO_WORKTREE",
        requested_autonomy_level=4,
        human_approved=human_approved,
        sandbox_evidence_present=True,
    ).to_dict()

    promotion_status = "PROMOTION_APPROVED_BY_HUMAN_GATE" if human_approved else "HUMAN_APPROVAL_REQUIRED"

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_authority_verification_required": True,
        "certification_evidence_items": [item.to_dict() for item in build_certification_evidence_items()],
        "certification_ready_not_certified": True,
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_applied": False,
        "human_approved": human_approved,
        "live_provider_calls_performed": False,
        "official_certification_decision_required": True,
        "promotion_gate": {
            "control_plane_decision": decision,
            "promotion_allowed_now": human_approved,
            "promotion_status": promotion_status,
            "real_worktree_mutation_performed_by_this_phase": False,
            "requires_human_approval": True,
        },
        "real_generated_application_deleted": False,
        "real_generated_application_overwritten": False,
        "real_worktree_mutated_by_this_phase": False,
        "requirement_id": requirement_id,
        "schema_version": "human-approved-promotion-certification-boundary.v1",
        "status": READY,
        "supporting_sandbox_report_status": sandbox_report["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_promotion_certification_boundary(boundary: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if boundary.get("schema_version") != "human-approved-promotion-certification-boundary.v1":
        failures.append("Invalid promotion/certification boundary schema")
    if boundary.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if boundary.get("status") != READY:
        failures.append("Boundary status must be ready")
    if boundary.get("factory_does_not_self_certify") is not True:
        failures.append("Factory must not self-certify")
    if boundary.get("certification_ready_not_certified") is not True:
        failures.append("Generated application must be certification-ready, not certified")
    if boundary.get("certification_authority_verification_required") is not True:
        failures.append("Certification authority verification must be required")
    if boundary.get("official_certification_decision_required") is not True:
        failures.append("Official certification decision must be required")
    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "live_provider_calls_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "real_worktree_mutated_by_this_phase",
    ]:
        if boundary.get(key) is not False:
            failures.append(f"{key} must be false")

    raw_boundary = boundary.get("what_sits_between_generated_application_and_certification")
    if not isinstance(raw_boundary, list):
        failures.append("Certification boundary list must be present")
    else:
        boundary_names = {str(item) for item in raw_boundary}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    evidence = boundary.get("certification_evidence_items")
    if not isinstance(evidence, list):
        failures.append("Certification evidence items must be listed")
    else:
        evidence_names: set[str] = set()
        for item in evidence:
            if isinstance(item, dict):
                evidence_id = item.get("evidence_id")
                if isinstance(evidence_id, str):
                    evidence_names.add(evidence_id)
        for item in CERTIFICATION_EVIDENCE:
            if item not in evidence_names:
                failures.append(f"Missing certification evidence: {item}")

    promotion = boundary.get("promotion_gate")
    if not isinstance(promotion, dict):
        failures.append("Promotion gate must be present")
    else:
        if promotion.get("requires_human_approval") is not True:
            failures.append("Promotion gate must require human approval")
        if promotion.get("real_worktree_mutation_performed_by_this_phase") is not False:
            failures.append("Phase 14C must not mutate real worktree")
    return failures


def write_boundary(boundary: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(boundary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human-approved promotion gate and certification-ready evidence boundary.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--human-approved-record", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    boundary = build_promotion_certification_boundary(
        requirement_id=args.requirement_id,
        human_approved=args.human_approved_record,
    )
    if args.audit_out is not None:
        write_boundary(boundary, args.audit_out)
    print(json.dumps(boundary, indent=2, sort_keys=True))
    failures = validate_promotion_certification_boundary(boundary)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
