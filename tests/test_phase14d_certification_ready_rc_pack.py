from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_certification_ready_release_candidate_evidence_pack import (
    READY,
    REQUIRED_SECTIONS,
    build_release_candidate_evidence_pack,
    validate_release_candidate_evidence_pack,
    write_evidence_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_release_candidate_pack_is_ready_not_certified() -> None:
    pack = build_release_candidate_evidence_pack()
    assert pack["status"] == READY
    assert pack["factory_does_not_self_certify"] is True
    assert pack["certification_ready_not_certified"] is True
    assert pack["official_certification_claimed"] is False
    assert validate_release_candidate_evidence_pack(pack) == []


def test_pack_lists_boundary_between_generated_app_and_certification() -> None:
    pack = build_release_candidate_evidence_pack()
    boundary_value = pack["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_pack_contains_required_evidence_sections() -> None:
    pack = build_release_candidate_evidence_pack()
    sections_value = pack["evidence_sections"]
    assert isinstance(sections_value, list)
    section_ids: set[str] = set()
    for section in sections_value:
        assert isinstance(section, dict)
        section_id = section["section_id"]
        assert isinstance(section_id, str)
        section_ids.add(section_id)
    assert section_ids == set(REQUIRED_SECTIONS)


def test_pack_does_not_execute_release_or_external_actions() -> None:
    pack = build_release_candidate_evidence_pack()
    assert pack["release_execution_performed"] is False
    assert pack["auto_merge_performed"] is False
    assert pack["auto_tag_performed"] is False
    assert pack["auto_release_performed"] is False
    assert pack["live_provider_calls_performed"] is False
    assert pack["external_system_calls_performed"] is False


def test_pack_references_supporting_phase_outputs() -> None:
    pack = build_release_candidate_evidence_pack()
    assert pack["supporting_boundary_status"] == "HUMAN_APPROVED_PROMOTION_CERTIFICATION_BOUNDARY_READY"
    assert pack["supporting_sandbox_status"] == "SANDBOX_AUTONOMOUS_GENERATION_VALIDATION_READY"


def test_evidence_pack_report_is_written(tmp_path: Path) -> None:
    pack = build_release_candidate_evidence_pack()
    output = tmp_path / "rc_pack.json"
    write_evidence_pack(pack, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "certification-ready-release-candidate-evidence-pack.v1"
    assert payload["status"] == READY


def test_phase14d_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14d_certification_ready_rc_pack.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14D certification-ready release candidate evidence pack artifacts validated." in result.stdout


def test_release_candidate_pack_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_certification_ready_release_candidate_evidence_pack.py",
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
