from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_certification_readiness_dashboard_index import (
    DASHBOARD_CARDS,
    READY,
    build_certification_readiness_dashboard_index,
    validate_certification_readiness_dashboard_index,
    write_dashboard_index,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_dashboard_index_is_ready_not_certified() -> None:
    index = build_certification_readiness_dashboard_index()
    assert index["status"] == READY
    assert index["factory_does_not_self_certify"] is True
    assert index["certification_ready_not_certified"] is True
    assert index["official_certification_claimed"] is False
    assert index["official_certification_granted_by_factory"] is False
    assert validate_certification_readiness_dashboard_index(index) == []


def test_dashboard_index_contains_required_cards() -> None:
    index = build_certification_readiness_dashboard_index()
    cards_value = index["dashboard_cards"]
    assert isinstance(cards_value, list)
    card_ids: set[str] = set()
    for card in cards_value:
        assert isinstance(card, dict)
        card_id = card["card_id"]
        assert isinstance(card_id, str)
        card_ids.add(card_id)
    assert card_ids == set(DASHBOARD_CARDS)


def test_dashboard_index_lists_certification_boundary() -> None:
    index = build_certification_readiness_dashboard_index()
    boundary_value = index["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_dashboard_index_does_not_release_or_call_external_systems() -> None:
    index = build_certification_readiness_dashboard_index()
    assert index["release_execution_performed"] is False
    assert index["auto_merge_performed"] is False
    assert index["auto_tag_performed"] is False
    assert index["auto_release_performed"] is False
    assert index["live_provider_calls_performed"] is False
    assert index["external_system_calls_performed"] is False


def test_dashboard_index_references_phase14d_to_phase14h_ready_statuses() -> None:
    index = build_certification_readiness_dashboard_index()
    assert index["supporting_evidence_pack_status"] == "CERTIFICATION_READY_RELEASE_CANDIDATE_EVIDENCE_PACK_READY"
    assert index["supporting_replay_pack_status"] == "FRESH_RECIPIENT_CERTIFICATION_EVIDENCE_REPLAY_READY"
    assert index["supporting_review_workspace_status"] == "CERTIFYING_AUTHORITY_REVIEW_WORKSPACE_READY"
    assert index["supporting_findings_loop_status"] == "AUTHORITY_FINDINGS_REMEDIATION_LOOP_READY"
    assert index["supporting_submission_dossier_status"] == "CERTIFICATION_AUTHORITY_SUBMISSION_DOSSIER_READY"


def test_dashboard_index_report_is_written(tmp_path: Path) -> None:
    index = build_certification_readiness_dashboard_index()
    output = tmp_path / "certification_readiness_dashboard_index.json"
    write_dashboard_index(index, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "certification-readiness-dashboard-index.v1"
    assert payload["status"] == READY


def test_phase14i_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14i_certification_readiness_dashboard_index.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14I certification readiness dashboard index artifacts validated." in result.stdout


def test_dashboard_index_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_certification_readiness_dashboard_index.py",
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
