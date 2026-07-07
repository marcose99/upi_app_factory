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
from scripts.build_certification_authority_submission_dossier import (
    READY as PHASE14H_READY,
    build_certification_authority_submission_dossier,
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
READY = "CERTIFICATION_READINESS_DASHBOARD_INDEX_READY"

DASHBOARD_CARDS: tuple[str, ...] = (
    "certification_boundary",
    "evidence_pack",
    "fresh_recipient_replay",
    "authority_review_workspace",
    "findings_remediation_loop",
    "submission_dossier",
    "official_decision_boundary",
    "safety_controls",
)


@dataclass(frozen=True)
class DashboardCard:
    card_id: str
    status: str
    source: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "source": self.source,
            "status": self.status,
            "summary": self.summary,
        }


def build_dashboard_cards() -> tuple[DashboardCard, ...]:
    return (
        DashboardCard("certification_boundary", "READY", "phase14c", "Generated application is certification-ready, not certified."),
        DashboardCard("evidence_pack", "READY", "phase14d", "Certification-ready release-candidate evidence pack is available."),
        DashboardCard("fresh_recipient_replay", "READY", "phase14e", "Fresh-recipient replay pack is available for independent verification."),
        DashboardCard("authority_review_workspace", "READY", "phase14f", "Authority review workspace is prepared without granting certification."),
        DashboardCard("findings_remediation_loop", "READY", "phase14g", "Authority findings and remediation loop is prepared."),
        DashboardCard("submission_dossier", "READY", "phase14h", "Authority-facing submission dossier is prepared."),
        DashboardCard("official_decision_boundary", "AUTHORITY_ONLY", "phase14c_phase14h_phase14i", "Official certification decision remains outside the factory."),
        DashboardCard("safety_controls", "READY", "phase14i", "No release, live calls, external calls, or automatic certification actions are performed."),
    )


def build_certification_readiness_dashboard_index(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    evidence_pack = build_release_candidate_evidence_pack(requirement_id=requirement_id)
    replay_pack = build_fresh_recipient_replay_pack(requirement_id=requirement_id)
    review_workspace = build_certifying_authority_review_workspace(requirement_id=requirement_id)
    findings_loop = build_authority_findings_remediation_loop(requirement_id=requirement_id)
    submission_dossier = build_certification_authority_submission_dossier(requirement_id=requirement_id)

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
        "dashboard_cards": [card.to_dict() for card in build_dashboard_cards()],
        "dashboard_index_only": True,
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_applied": False,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_decision_required": True,
        "official_certification_granted_by_factory": False,
        "recommended_operator_portal_panels": list(DASHBOARD_CARDS),
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "certification-readiness-dashboard-index.v1",
        "status": READY,
        "supporting_evidence_pack_expected_status": PHASE14D_READY,
        "supporting_evidence_pack_status": evidence_pack["status"],
        "supporting_findings_loop_expected_status": PHASE14G_READY,
        "supporting_findings_loop_status": findings_loop["status"],
        "supporting_replay_pack_expected_status": PHASE14E_READY,
        "supporting_replay_pack_status": replay_pack["status"],
        "supporting_review_workspace_expected_status": PHASE14F_READY,
        "supporting_review_workspace_status": review_workspace["status"],
        "supporting_submission_dossier_expected_status": PHASE14H_READY,
        "supporting_submission_dossier_status": submission_dossier["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_certification_readiness_dashboard_index(index: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if index.get("schema_version") != "certification-readiness-dashboard-index.v1":
        failures.append("Invalid certification readiness dashboard index schema")
    if index.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if index.get("status") != READY:
        failures.append("Dashboard index must be ready")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "dashboard_index_only",
    ]:
        if index.get(key) is not True:
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
        if index.get(key) is not False:
            failures.append(f"{key} must be false")

    cards_value = index.get("dashboard_cards")
    if not isinstance(cards_value, list):
        failures.append("Dashboard cards must be listed")
    else:
        card_ids: set[str] = set()
        for card in cards_value:
            if isinstance(card, dict):
                card_id = card.get("card_id")
                if isinstance(card_id, str):
                    card_ids.add(card_id)
        for card_id in DASHBOARD_CARDS:
            if card_id not in card_ids:
                failures.append(f"Missing dashboard card: {card_id}")

    boundary_value = index.get("what_sits_between_generated_application_and_certification")
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
        "supporting_submission_dossier_status": PHASE14H_READY,
    }
    for key, expected in expected_statuses.items():
        if index.get(key) != expected:
            failures.append(f"{key} must be {expected}")
    return failures


def write_dashboard_index(index: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build certification readiness dashboard index.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    index = build_certification_readiness_dashboard_index(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_dashboard_index(index, args.audit_out)
    print(json.dumps(index, indent=2, sort_keys=True))
    failures = validate_certification_readiness_dashboard_index(index)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
