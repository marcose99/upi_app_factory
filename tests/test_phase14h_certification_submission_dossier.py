from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_certification_authority_submission_dossier import (
    DOSSIER_SECTIONS,
    READY,
    build_certification_authority_submission_dossier,
    validate_certification_authority_submission_dossier,
    write_submission_dossier,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_submission_dossier_is_ready_not_certified() -> None:
    dossier = build_certification_authority_submission_dossier()
    assert dossier["status"] == READY
    assert dossier["factory_does_not_self_certify"] is True
    assert dossier["certification_ready_not_certified"] is True
    assert dossier["official_certification_claimed"] is False
    assert dossier["official_certification_granted_by_factory"] is False
    assert validate_certification_authority_submission_dossier(dossier) == []


def test_submission_dossier_contains_required_sections() -> None:
    dossier = build_certification_authority_submission_dossier()
    sections_value = dossier["dossier_sections"]
    assert isinstance(sections_value, list)
    section_ids: set[str] = set()
    for section in sections_value:
        assert isinstance(section, dict)
        section_id = section["section_id"]
        assert isinstance(section_id, str)
        section_ids.add(section_id)
    assert section_ids == set(DOSSIER_SECTIONS)


def test_submission_dossier_lists_certification_boundary() -> None:
    dossier = build_certification_authority_submission_dossier()
    boundary_value = dossier["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_submission_dossier_does_not_release_or_call_external_systems() -> None:
    dossier = build_certification_authority_submission_dossier()
    assert dossier["release_execution_performed"] is False
    assert dossier["auto_merge_performed"] is False
    assert dossier["auto_tag_performed"] is False
    assert dossier["auto_release_performed"] is False
    assert dossier["live_provider_calls_performed"] is False
    assert dossier["external_system_calls_performed"] is False


def test_submission_dossier_references_phase14d_to_phase14g_ready_statuses() -> None:
    dossier = build_certification_authority_submission_dossier()
    assert dossier["supporting_evidence_pack_status"] == "CERTIFICATION_READY_RELEASE_CANDIDATE_EVIDENCE_PACK_READY"
    assert dossier["supporting_replay_pack_status"] == "FRESH_RECIPIENT_CERTIFICATION_EVIDENCE_REPLAY_READY"
    assert dossier["supporting_review_workspace_status"] == "CERTIFYING_AUTHORITY_REVIEW_WORKSPACE_READY"
    assert dossier["supporting_findings_loop_status"] == "AUTHORITY_FINDINGS_REMEDIATION_LOOP_READY"


def test_submission_dossier_report_is_written(tmp_path: Path) -> None:
    dossier = build_certification_authority_submission_dossier()
    output = tmp_path / "certification_authority_submission_dossier.json"
    write_submission_dossier(dossier, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "certification-authority-submission-dossier.v1"
    assert payload["status"] == READY


def test_phase14h_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14h_certification_submission_dossier.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14H certification authority submission dossier artifacts validated." in result.stdout


def test_submission_dossier_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_certification_authority_submission_dossier.py",
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
