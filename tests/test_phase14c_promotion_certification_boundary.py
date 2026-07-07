from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_human_approved_promotion_certification_boundary import (
    CERTIFICATION_BOUNDARY,
    CERTIFICATION_EVIDENCE,
    READY,
    build_promotion_certification_boundary,
    validate_promotion_certification_boundary,
    write_boundary,
)


def test_boundary_is_ready_and_not_self_certified() -> None:
    boundary = build_promotion_certification_boundary()
    assert boundary["status"] == READY
    assert boundary["factory_does_not_self_certify"] is True
    assert boundary["certification_ready_not_certified"] is True
    assert boundary["certification_authority_verification_required"] is True
    assert validate_promotion_certification_boundary(boundary) == []


def test_boundary_lists_what_sits_between_app_and_certification() -> None:
    boundary = build_promotion_certification_boundary()
    items_value = boundary["what_sits_between_generated_application_and_certification"]
    assert isinstance(items_value, list)
    assert set(items_value) == set(CERTIFICATION_BOUNDARY)


def test_certification_evidence_items_are_complete() -> None:
    boundary = build_promotion_certification_boundary()
    evidence_value = boundary["certification_evidence_items"]
    assert isinstance(evidence_value, list)
    evidence_ids: set[str] = set()
    for item in evidence_value:
        assert isinstance(item, dict)
        evidence_id = item["evidence_id"]
        assert isinstance(evidence_id, str)
        evidence_ids.add(evidence_id)
    assert evidence_ids == set(CERTIFICATION_EVIDENCE)


def test_promotion_requires_human_approval_by_default() -> None:
    boundary = build_promotion_certification_boundary()
    promotion_value = boundary["promotion_gate"]
    assert isinstance(promotion_value, dict)
    assert promotion_value["requires_human_approval"] is True
    assert promotion_value["promotion_allowed_now"] is False
    assert promotion_value["real_worktree_mutation_performed_by_this_phase"] is False


def test_human_approved_record_allows_decision_but_not_mutation() -> None:
    boundary = build_promotion_certification_boundary(human_approved=True)
    promotion_value = boundary["promotion_gate"]
    assert isinstance(promotion_value, dict)
    assert promotion_value["promotion_allowed_now"] is True
    assert promotion_value["real_worktree_mutation_performed_by_this_phase"] is False


def test_no_release_or_external_actions_are_performed() -> None:
    boundary = build_promotion_certification_boundary()
    assert boundary["auto_merge_performed"] is False
    assert boundary["auto_tag_performed"] is False
    assert boundary["auto_release_performed"] is False
    assert boundary["live_provider_calls_performed"] is False
    assert boundary["external_system_calls_performed"] is False


def test_boundary_report_is_written(tmp_path: Path) -> None:
    boundary = build_promotion_certification_boundary()
    output = tmp_path / "boundary.json"
    write_boundary(boundary, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "human-approved-promotion-certification-boundary.v1"
    assert payload["status"] == READY


def test_phase14c_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14c_promotion_certification_boundary.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14C human-approved promotion and certification boundary artifacts validated." in result.stdout


def test_boundary_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_human_approved_promotion_certification_boundary.py",
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
