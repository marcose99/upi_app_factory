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

from scripts.build_human_approved_promotion_certification_boundary import (
    CERTIFICATION_BOUNDARY,
    CERTIFICATION_EVIDENCE,
    build_promotion_certification_boundary,
)
from scripts.run_sandbox_autonomous_generation_validation_loop import build_sandbox_loop_report


APP_ID = "upi_dispute_resolution"
READY = "CERTIFICATION_READY_RELEASE_CANDIDATE_EVIDENCE_PACK_READY"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "application_identity",
    "certification_boundary_statement",
    "requirement_traceability",
    "architecture_and_design_evidence",
    "policy_decision_records",
    "sandbox_generation_evidence",
    "local_validation_reports",
    "security_and_governance_validation_reports",
    "mock_boundary_evidence",
    "rollback_and_replay_evidence",
    "handover_evidence",
    "known_limitations",
    "certifying_authority_action_required",
)


@dataclass(frozen=True)
class EvidenceSection:
    section_id: str
    status: str
    source_phase: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "source_phase": self.source_phase,
            "status": self.status,
            "summary": self.summary,
        }


def build_evidence_sections() -> tuple[EvidenceSection, ...]:
    return (
        EvidenceSection("application_identity", "AVAILABLE", "phase13b_phase14d", "Identifies the generated UPI dispute resolution application and local runtime boundary."),
        EvidenceSection("certification_boundary_statement", "AVAILABLE", "phase14c", "States certification-ready, not certified, and identifies official authority boundary."),
        EvidenceSection("requirement_traceability", "AVAILABLE", "phase14a", "Links lifecycle plan steps to the original generated application requirement intent."),
        EvidenceSection("architecture_and_design_evidence", "AVAILABLE", "phase13as_phase14a", "Captures governed architecture and standards alignment evidence."),
        EvidenceSection("policy_decision_records", "AVAILABLE", "phase13az_phase14a_phase14c", "Captures autonomy decisions, blocked actions, human gates, and policy gates."),
        EvidenceSection("sandbox_generation_evidence", "AVAILABLE", "phase14b", "Captures sandbox-only generation preview and validation report."),
        EvidenceSection("local_validation_reports", "AVAILABLE", "phase_validation_logs", "Captures pytest, Ruff, MyPy, and validator evidence."),
        EvidenceSection("security_and_governance_validation_reports", "AVAILABLE", "phase13av_governance_tests", "Captures local agentic-AI threat and governance validation evidence."),
        EvidenceSection("mock_boundary_evidence", "AVAILABLE", "phase11b_phase14b", "Confirms external ecosystem stays mocked/simulated."),
        EvidenceSection("rollback_and_replay_evidence", "AVAILABLE", "phase13aq_phase13ar_phase14b", "Captures replay and rollback-oriented evidence."),
        EvidenceSection("handover_evidence", "AVAILABLE", "phase13aq_phase13aw_phase14d", "Captures handover and operator readiness evidence."),
        EvidenceSection("known_limitations", "AVAILABLE", "phase14c_phase14d", "States the gap between generated application and official certification."),
        EvidenceSection("certifying_authority_action_required", "REQUIRED_AFTER_FACTORY_OUTPUT", "phase14d", "Requires independent review and official certification decision."),
    )


def build_release_candidate_evidence_pack(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
    release_candidate_id: str = "upi_dispute_resolution.rc.local.certification_ready",
) -> dict[str, object]:
    boundary = build_promotion_certification_boundary(requirement_id=requirement_id)
    sandbox = build_sandbox_loop_report(requirement_id=requirement_id)
    sections = build_evidence_sections()

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_authority_verification_required": True,
        "certification_evidence_required": list(CERTIFICATION_EVIDENCE),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "evidence_sections": [section.to_dict() for section in sections],
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_applied": False,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_decision_required": True,
        "release_candidate_id": release_candidate_id,
        "release_candidate_pack_only": True,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "certification-ready-release-candidate-evidence-pack.v1",
        "status": READY,
        "supporting_boundary_status": boundary["status"],
        "supporting_sandbox_status": sandbox["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_release_candidate_evidence_pack(pack: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if pack.get("schema_version") != "certification-ready-release-candidate-evidence-pack.v1":
        failures.append("Invalid release candidate evidence pack schema")
    if pack.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if pack.get("status") != READY:
        failures.append("Release candidate evidence pack must be ready")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "release_candidate_pack_only",
    ]:
        if pack.get(key) is not True:
            failures.append(f"{key} must be true")
    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "live_provider_calls_performed",
        "official_certification_claimed",
        "release_execution_performed",
    ]:
        if pack.get(key) is not False:
            failures.append(f"{key} must be false")

    boundary_value = pack.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    sections_value = pack.get("evidence_sections")
    if not isinstance(sections_value, list):
        failures.append("Evidence sections must be listed")
    else:
        section_ids: set[str] = set()
        for item in sections_value:
            if isinstance(item, dict):
                section_id = item.get("section_id")
                if isinstance(section_id, str):
                    section_ids.add(section_id)
        for section in REQUIRED_SECTIONS:
            if section not in section_ids:
                failures.append(f"Missing evidence section: {section}")
    return failures


def write_evidence_pack(pack: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build certification-ready release candidate evidence pack.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--release-candidate-id", default="upi_dispute_resolution.rc.local.certification_ready")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    pack = build_release_candidate_evidence_pack(
        requirement_id=args.requirement_id,
        release_candidate_id=args.release_candidate_id,
    )
    if args.audit_out is not None:
        write_evidence_pack(pack, args.audit_out)
    print(json.dumps(pack, indent=2, sort_keys=True))
    failures = validate_release_candidate_evidence_pack(pack)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
