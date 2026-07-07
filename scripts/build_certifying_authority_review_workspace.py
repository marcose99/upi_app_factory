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

from scripts.build_certification_ready_release_candidate_evidence_pack import (
    READY as PHASE14D_READY,
    REQUIRED_SECTIONS as PHASE14D_SECTIONS,
    build_release_candidate_evidence_pack,
)
from scripts.build_fresh_recipient_certification_evidence_replay_pack import (
    READY as PHASE14E_READY,
    REPLAY_STEPS,
    build_fresh_recipient_replay_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


APP_ID = "upi_dispute_resolution"
READY = "CERTIFYING_AUTHORITY_REVIEW_WORKSPACE_READY"

REVIEW_SECTIONS: tuple[str, ...] = (
    "authority_identity_placeholder",
    "scope_of_review",
    "evidence_inventory",
    "fresh_recipient_replay_results",
    "certification_boundary",
    "findings_register",
    "open_items_register",
    "production_environment_validation_needed",
    "official_decision_placeholder",
)


@dataclass(frozen=True)
class ReviewSection:
    section_id: str
    status: str
    owner: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "owner": self.owner,
            "section_id": self.section_id,
            "status": self.status,
            "summary": self.summary,
        }


def build_review_sections() -> tuple[ReviewSection, ...]:
    return (
        ReviewSection("authority_identity_placeholder", "PENDING_AUTHORITY_INPUT", "certifying_authority", "Captures authorized reviewer identity outside the factory."),
        ReviewSection("scope_of_review", "READY_FOR_REVIEW", "factory", "Defines certification-ready local generated application and mock ecosystem boundary."),
        ReviewSection("evidence_inventory", "READY_FOR_REVIEW", "factory", "Indexes Phase 14D evidence sections for independent review."),
        ReviewSection("fresh_recipient_replay_results", "READY_FOR_REVIEW", "factory", "Indexes Phase 14E replay steps and expected verification outcomes."),
        ReviewSection("certification_boundary", "READY_FOR_REVIEW", "factory", "States generated application is certification-ready, not certified."),
        ReviewSection("findings_register", "PENDING_AUTHORITY_INPUT", "certifying_authority", "Captures reviewer findings without factory self-approval."),
        ReviewSection("open_items_register", "PENDING_AUTHORITY_INPUT", "certifying_authority", "Captures gaps or required remediation from independent review."),
        ReviewSection("production_environment_validation_needed", "PENDING_CONTEXT", "certifying_authority", "Captures any required production-environment validation."),
        ReviewSection("official_decision_placeholder", "PENDING_AUTHORITY_DECISION", "certifying_authority", "Reserved for official certification decision outside the factory."),
    )


def build_certifying_authority_review_workspace(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    evidence_pack = build_release_candidate_evidence_pack(requirement_id=requirement_id)
    replay_pack = build_fresh_recipient_replay_pack(requirement_id=requirement_id)

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_authority_verification_required": True,
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "evidence_inventory_sections": list(PHASE14D_SECTIONS),
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_applied": False,
        "fresh_recipient_replay_steps": list(REPLAY_STEPS),
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_decision_required": True,
        "official_certification_granted_by_factory": False,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "review_sections": [section.to_dict() for section in build_review_sections()],
        "review_workspace_only": True,
        "schema_version": "certifying-authority-review-workspace.v1",
        "status": READY,
        "supporting_evidence_pack_status": evidence_pack["status"],
        "supporting_evidence_pack_expected_status": PHASE14D_READY,
        "supporting_replay_pack_status": replay_pack["status"],
        "supporting_replay_pack_expected_status": PHASE14E_READY,
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_certifying_authority_review_workspace(workspace: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if workspace.get("schema_version") != "certifying-authority-review-workspace.v1":
        failures.append("Invalid certifying authority workspace schema")
    if workspace.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if workspace.get("status") != READY:
        failures.append("Review workspace must be ready")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "review_workspace_only",
    ]:
        if workspace.get(key) is not True:
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
        "official_certification_granted_by_factory",
        "release_execution_performed",
    ]:
        if workspace.get(key) is not False:
            failures.append(f"{key} must be false")

    sections_value = workspace.get("review_sections")
    if not isinstance(sections_value, list):
        failures.append("Review sections must be listed")
    else:
        section_ids: set[str] = set()
        for section in sections_value:
            if isinstance(section, dict):
                section_id = section.get("section_id")
                if isinstance(section_id, str):
                    section_ids.add(section_id)
        for section_id in REVIEW_SECTIONS:
            if section_id not in section_ids:
                failures.append(f"Missing review section: {section_id}")

    boundary_value = workspace.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if workspace.get("supporting_evidence_pack_status") != PHASE14D_READY:
        failures.append("Supporting Phase 14D evidence pack must be ready")
    if workspace.get("supporting_replay_pack_status") != PHASE14E_READY:
        failures.append("Supporting Phase 14E replay pack must be ready")
    return failures


def write_review_workspace(workspace: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(workspace, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build certifying authority review workspace.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    workspace = build_certifying_authority_review_workspace(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_review_workspace(workspace, args.audit_out)
    print(json.dumps(workspace, indent=2, sort_keys=True))
    failures = validate_certifying_authority_review_workspace(workspace)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
