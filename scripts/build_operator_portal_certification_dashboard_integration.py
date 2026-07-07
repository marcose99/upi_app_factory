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
    DASHBOARD_CARDS as PHASE14I_CARDS,
    READY as PHASE14I_READY,
    build_certification_readiness_dashboard_index,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.run_governed_autonomous_phase_execution_loop import (
    READY as PHASE14K_READY,
    build_governed_autonomous_phase_execution_loop,
)


APP_ID = "upi_dispute_resolution"
READY = "OPERATOR_PORTAL_CERTIFICATION_READINESS_DASHBOARD_INTEGRATION_READY"

PORTAL_CARDS: tuple[str, ...] = (
    "certification_boundary",
    "evidence_pack",
    "fresh_recipient_replay",
    "authority_review_workspace",
    "findings_remediation_loop",
    "submission_dossier",
    "official_decision_boundary",
    "safety_controls",
    "governed_autonomous_execution",
)

RECOMMENDED_ROUTES: tuple[str, ...] = (
    "/dashboards/certification-readiness",
    "/api/dashboards/certification-readiness",
    "/api/certification-readiness",
)

OPERATOR_VISIBLE_WORDING: tuple[str, ...] = (
    "Certification-ready, not certified.",
    "Factory does not self-certify.",
    "Official certification decision remains with authorized certifying authorities.",
)


@dataclass(frozen=True)
class PortalCard:
    card_id: str
    display_title: str
    source_phase: str
    status: str
    operator_wording: str

    def to_dict(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "display_title": self.display_title,
            "operator_wording": self.operator_wording,
            "source_phase": self.source_phase,
            "status": self.status,
        }


def build_portal_cards() -> tuple[PortalCard, ...]:
    return (
        PortalCard("certification_boundary", "Certification Boundary", "14C-14L", "READY", "Certification-ready, not certified."),
        PortalCard("evidence_pack", "Evidence Pack", "14D", "READY", "Evidence pack is prepared for independent review."),
        PortalCard("fresh_recipient_replay", "Fresh Recipient Replay", "14E", "READY", "Replay evidence can be independently verified."),
        PortalCard("authority_review_workspace", "Authority Review Workspace", "14F", "READY", "Authority review workspace is prepared."),
        PortalCard("findings_remediation_loop", "Findings and Remediation", "14G", "READY", "Authority findings can be tracked without self-certification."),
        PortalCard("submission_dossier", "Submission Dossier", "14H", "READY", "Authority-facing dossier is prepared."),
        PortalCard("official_decision_boundary", "Official Decision Boundary", "14H-14L", "AUTHORITY_ONLY", "Official certification decision remains outside the factory."),
        PortalCard("safety_controls", "Safety Controls", "14I-14L", "READY", "No release, live calls, or certification claims are performed."),
        PortalCard("governed_autonomous_execution", "Governed Autonomous Execution", "14K", "READY", "Autonomous execution stops at human approval gates."),
    )


def build_operator_portal_certification_dashboard_integration(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    dashboard_index = build_certification_readiness_dashboard_index(requirement_id=requirement_id)
    execution_loop = build_governed_autonomous_phase_execution_loop(requirement_id=requirement_id)

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_tag": True,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "operator_visible_status_must_be_not_certified": True,
        "operator_visible_wording": list(OPERATOR_VISIBLE_WORDING),
        "portal_cards": [card.to_dict() for card in build_portal_cards()],
        "portal_integration_contract_only": True,
        "recommended_routes": list(RECOMMENDED_ROUTES),
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "operator-portal-certification-dashboard-integration.v1",
        "status": READY,
        "supporting_dashboard_index_expected_status": PHASE14I_READY,
        "supporting_dashboard_index_status": dashboard_index["status"],
        "supporting_execution_loop_expected_status": PHASE14K_READY,
        "supporting_execution_loop_status": execution_loop["status"],
        "supporting_phase14i_card_ids": list(PHASE14I_CARDS),
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_operator_portal_certification_dashboard_integration(
    integration: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    if integration.get("schema_version") != "operator-portal-certification-dashboard-integration.v1":
        failures.append("Invalid operator portal certification dashboard integration schema")
    if integration.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if integration.get("status") != READY:
        failures.append("Portal dashboard integration must be ready")

    for key in [
        "portal_integration_contract_only",
        "operator_visible_status_must_be_not_certified",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]:
        if integration.get(key) is not True:
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
        if integration.get(key) is not False:
            failures.append(f"{key} must be false")

    cards_value = integration.get("portal_cards")
    if not isinstance(cards_value, list):
        failures.append("Portal cards must be listed")
    else:
        card_ids: set[str] = set()
        for card in cards_value:
            if isinstance(card, dict):
                card_id = card.get("card_id")
                if isinstance(card_id, str):
                    card_ids.add(card_id)
        for card_id in PORTAL_CARDS:
            if card_id not in card_ids:
                failures.append(f"Missing portal card: {card_id}")

    routes_value = integration.get("recommended_routes")
    if not isinstance(routes_value, list):
        failures.append("Recommended routes must be listed")
    else:
        route_names = {str(item) for item in routes_value}
        for route in RECOMMENDED_ROUTES:
            if route not in route_names:
                failures.append(f"Missing recommended route: {route}")

    wording_value = integration.get("operator_visible_wording")
    if not isinstance(wording_value, list):
        failures.append("Operator visible wording must be listed")
    else:
        wording_names = {str(item) for item in wording_value}
        for phrase in OPERATOR_VISIBLE_WORDING:
            if phrase not in wording_names:
                failures.append(f"Missing operator wording: {phrase}")

    boundary_value = integration.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if integration.get("supporting_dashboard_index_status") != PHASE14I_READY:
        failures.append("Supporting Phase 14I dashboard index must be ready")
    if integration.get("supporting_execution_loop_status") != PHASE14K_READY:
        failures.append("Supporting Phase 14K execution loop must be ready")
    return failures


def write_portal_integration(integration: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(integration, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build operator portal certification readiness dashboard integration."
    )
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    integration = build_operator_portal_certification_dashboard_integration(
        requirement_id=args.requirement_id
    )
    if args.audit_out is not None:
        write_portal_integration(integration, args.audit_out)
    print(json.dumps(integration, indent=2, sort_keys=True))
    failures = validate_operator_portal_certification_dashboard_integration(integration)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
