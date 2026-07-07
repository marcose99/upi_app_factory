from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_certifying_authority_review_workspace import (
    READY,
    REVIEW_SECTIONS,
    build_certifying_authority_review_workspace,
    validate_certifying_authority_review_workspace,
    write_review_workspace,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_review_workspace_is_ready_not_certified() -> None:
    workspace = build_certifying_authority_review_workspace()
    assert workspace["status"] == READY
    assert workspace["factory_does_not_self_certify"] is True
    assert workspace["certification_ready_not_certified"] is True
    assert workspace["official_certification_claimed"] is False
    assert workspace["official_certification_granted_by_factory"] is False
    assert validate_certifying_authority_review_workspace(workspace) == []


def test_review_workspace_contains_required_sections() -> None:
    workspace = build_certifying_authority_review_workspace()
    sections_value = workspace["review_sections"]
    assert isinstance(sections_value, list)
    section_ids: set[str] = set()
    for section in sections_value:
        assert isinstance(section, dict)
        section_id = section["section_id"]
        assert isinstance(section_id, str)
        section_ids.add(section_id)
    assert section_ids == set(REVIEW_SECTIONS)


def test_review_workspace_lists_certification_boundary() -> None:
    workspace = build_certifying_authority_review_workspace()
    boundary_value = workspace["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_review_workspace_does_not_release_or_call_external_systems() -> None:
    workspace = build_certifying_authority_review_workspace()
    assert workspace["release_execution_performed"] is False
    assert workspace["auto_merge_performed"] is False
    assert workspace["auto_tag_performed"] is False
    assert workspace["auto_release_performed"] is False
    assert workspace["live_provider_calls_performed"] is False
    assert workspace["external_system_calls_performed"] is False


def test_review_workspace_references_phase14d_and_phase14e_ready_statuses() -> None:
    workspace = build_certifying_authority_review_workspace()
    assert workspace["supporting_evidence_pack_status"] == "CERTIFICATION_READY_RELEASE_CANDIDATE_EVIDENCE_PACK_READY"
    assert workspace["supporting_replay_pack_status"] == "FRESH_RECIPIENT_CERTIFICATION_EVIDENCE_REPLAY_READY"


def test_review_workspace_report_is_written(tmp_path: Path) -> None:
    workspace = build_certifying_authority_review_workspace()
    output = tmp_path / "certifying_authority_workspace.json"
    write_review_workspace(workspace, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "certifying-authority-review-workspace.v1"
    assert payload["status"] == READY


def test_phase14f_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14f_certifying_authority_workspace.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14F certifying authority review workspace artifacts validated." in result.stdout


def test_review_workspace_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_certifying_authority_review_workspace.py",
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
