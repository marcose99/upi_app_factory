from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_certification_dashboard_integration import (
    OPERATOR_VISIBLE_WORDING,
    PORTAL_CARDS,
    READY,
    RECOMMENDED_ROUTES,
    build_operator_portal_certification_dashboard_integration,
    validate_operator_portal_certification_dashboard_integration,
    write_portal_integration,
)


def test_portal_integration_is_ready_and_not_certified() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    assert integration["status"] == READY
    assert integration["portal_integration_contract_only"] is True
    assert integration["operator_visible_status_must_be_not_certified"] is True
    assert integration["factory_does_not_self_certify"] is True
    assert integration["certification_ready_not_certified"] is True
    assert integration["official_certification_claimed"] is False
    assert integration["official_certification_granted_by_factory"] is False
    assert validate_operator_portal_certification_dashboard_integration(integration) == []


def test_portal_integration_lists_required_cards() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    cards_value = integration["portal_cards"]
    assert isinstance(cards_value, list)
    card_ids: set[str] = set()
    for card in cards_value:
        assert isinstance(card, dict)
        card_id = card["card_id"]
        assert isinstance(card_id, str)
        card_ids.add(card_id)
    assert card_ids == set(PORTAL_CARDS)


def test_portal_integration_lists_routes_and_wording() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    routes_value = integration["recommended_routes"]
    wording_value = integration["operator_visible_wording"]
    assert isinstance(routes_value, list)
    assert isinstance(wording_value, list)
    assert set(routes_value) == set(RECOMMENDED_ROUTES)
    assert set(wording_value) == set(OPERATOR_VISIBLE_WORDING)


def test_portal_integration_preserves_certification_boundary() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    boundary_value = integration["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_portal_integration_preserves_human_gates() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    assert integration["human_approval_required_for_promotion"] is True
    assert integration["human_approval_required_for_merge"] is True
    assert integration["human_approval_required_for_tag"] is True
    assert integration["human_approval_required_for_release"] is True


def test_portal_integration_does_not_release_or_call_external_systems() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    assert integration["release_execution_performed"] is False
    assert integration["auto_merge_performed"] is False
    assert integration["auto_tag_performed"] is False
    assert integration["auto_release_performed"] is False
    assert integration["live_provider_calls_performed"] is False
    assert integration["external_system_calls_performed"] is False
    assert integration["arbitrary_shell_execution_performed"] is False


def test_portal_integration_references_phase14i_and_phase14k_ready_statuses() -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    assert integration["supporting_dashboard_index_status"] == "CERTIFICATION_READINESS_DASHBOARD_INDEX_READY"
    assert integration["supporting_execution_loop_status"] == "GOVERNED_AUTONOMOUS_PHASE_EXECUTION_LOOP_READY"


def test_portal_integration_report_is_written(tmp_path: Path) -> None:
    integration = build_operator_portal_certification_dashboard_integration()
    output = tmp_path / "operator_portal_certification_dashboard_integration.json"
    write_portal_integration(integration, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "operator-portal-certification-dashboard-integration.v1"
    assert payload["status"] == READY


def test_phase14l_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14l_operator_portal_certification_dashboard.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14L operator portal certification dashboard artifacts validated." in result.stdout


def test_portal_integration_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_operator_portal_certification_dashboard_integration.py",
            "--requirement-id",
            "upi_dispute_resolution.demo",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == READY
