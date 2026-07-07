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

from scripts.build_authority_findings_remediation_loop import (
    READY as PHASE14G_READY,
    build_authority_findings_remediation_loop,
)
from scripts.build_certification_ready_release_candidate_evidence_pack import (
    READY as PHASE14D_READY,
    build_release_candidate_evidence_pack,
)
from scripts.build_certifying_authority_review_workspace import (
    READY as PHASE14F_READY,
    build_certifying_authority_review_workspace,
)
from scripts.build_fresh_recipient_certification_evidence_replay_pack import (
    READY as PHASE14E_READY,
    build_fresh_recipient_replay_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


APP_ID = "upi_dispute_resolution"
READY = "CERTIFICATION_AUTHORITY_SUBMISSION_DOSSIER_READY"

DOSSIER_SECTIONS: tuple[str, ...] = (
    "submission_cover",
    "application_identity",
    "certification_boundary_statement",
    "evidence_inventory",
    "fresh_recipient_replay_summary",
    "authority_review_workspace_summary",
    "findings_remediation_summary",
    "production_environment_validation_checklist",
    "official_decision_placeholder",
    "factory_non_certification_attestation",
)


@dataclass(frozen=True)
class DossierSection:
    section_id: str
    status: str
    source: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "source": self.source,
            "status": self.status,
            "summary": self.summary,
        }


def build_dossier_sections() -> tuple[DossierSection, ...]:
    return (
        DossierSection("submission_cover", "READY_FOR_AUTHORITY_REVIEW", "phase14h", "Authority-facing cover and submission context."),
        DossierSection("application_identity", "READY_FOR_AUTHORITY_REVIEW", "phase14d", "Generated application identity and local runtime boundary."),
        DossierSection("certification_boundary_statement", "READY_FOR_AUTHORITY_REVIEW", "phase14c_phase14h", "Certification-ready, not certified; factory does not self-certify."),
        DossierSection("evidence_inventory", "READY_FOR_AUTHORITY_REVIEW", "phase14d", "Certification-ready evidence inventory."),
        DossierSection("fresh_recipient_replay_summary", "READY_FOR_AUTHORITY_REVIEW", "phase14e", "Fresh-recipient replay steps and evidence."),
        DossierSection("authority_review_workspace_summary", "READY_FOR_AUTHORITY_REVIEW", "phase14f", "Review workspace structure and authority-only fields."),
        DossierSection("findings_remediation_summary", "READY_FOR_AUTHORITY_REVIEW", "phase14g", "Findings, remediation, re-test, and re-review registers."),
        DossierSection("production_environment_validation_checklist", "PENDING_AUTHORITY_OR_PRODUCTION_CONTEXT", "phase14h", "Checklist for any required production validation outside local factory evidence."),
        DossierSection("official_decision_placeholder", "PENDING_AUTHORITY_DECISION", "certifying_authority", "Reserved for official authority certification decision."),
        DossierSection("factory_non_certification_attestation", "READY_FOR_AUTHORITY_REVIEW", "phase14h", "Factory attests it did not certify or grant certification."),
    )


def build_certification_authority_submission_dossier(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    evidence_pack = build_release_candidate_evidence_pack(requirement_id=requirement_id)
    replay_pack = build_fresh_recipient_replay_pack(requirement_id=requirement_id)
    review_workspace = build_certifying_authority_review_workspace(requirement_id=requirement_id)
    findings_loop = build_authority_findings_remediation_loop(requirement_id=requirement_id)

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
        "dossier_sections": [section.to_dict() for section in build_dossier_sections()],
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_non_certification_attestation": (
            "The factory generated certification-ready evidence only. It did not self-certify, "
            "grant certification, impersonate a certifying authority, or make an official certification decision."
        ),
        "factory_self_modification_applied": False,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_decision_required": True,
        "official_certification_granted_by_factory": False,
        "production_environment_validation_required_where_applicable": True,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "certification-authority-submission-dossier.v1",
        "status": READY,
        "submission_dossier_only": True,
        "supporting_evidence_pack_expected_status": PHASE14D_READY,
        "supporting_evidence_pack_status": evidence_pack["status"],
        "supporting_findings_loop_expected_status": PHASE14G_READY,
        "supporting_findings_loop_status": findings_loop["status"],
        "supporting_replay_pack_expected_status": PHASE14E_READY,
        "supporting_replay_pack_status": replay_pack["status"],
        "supporting_review_workspace_expected_status": PHASE14F_READY,
        "supporting_review_workspace_status": review_workspace["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_certification_authority_submission_dossier(dossier: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if dossier.get("schema_version") != "certification-authority-submission-dossier.v1":
        failures.append("Invalid certification authority submission dossier schema")
    if dossier.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if dossier.get("status") != READY:
        failures.append("Submission dossier must be ready")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "production_environment_validation_required_where_applicable",
        "submission_dossier_only",
    ]:
        if dossier.get(key) is not True:
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
        if dossier.get(key) is not False:
            failures.append(f"{key} must be false")

    sections_value = dossier.get("dossier_sections")
    if not isinstance(sections_value, list):
        failures.append("Dossier sections must be listed")
    else:
        section_ids: set[str] = set()
        for section in sections_value:
            if isinstance(section, dict):
                section_id = section.get("section_id")
                if isinstance(section_id, str):
                    section_ids.add(section_id)
        for section_id in DOSSIER_SECTIONS:
            if section_id not in section_ids:
                failures.append(f"Missing dossier section: {section_id}")

    boundary_value = dossier.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    expected_statuses = {
        "supporting_evidence_pack_status": PHASE14D_READY,
        "supporting_replay_pack_status": PHASE14E_READY,
        "supporting_review_workspace_status": PHASE14F_READY,
        "supporting_findings_loop_status": PHASE14G_READY,
    }
    for key, expected in expected_statuses.items():
        if dossier.get(key) != expected:
            failures.append(f"{key} must be {expected}")
    return failures


def write_submission_dossier(dossier: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(dossier, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build certification authority submission dossier.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    dossier = build_certification_authority_submission_dossier(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_submission_dossier(dossier, args.audit_out)
    print(json.dumps(dossier, indent=2, sort_keys=True))
    failures = validate_certification_authority_submission_dossier(dossier)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
