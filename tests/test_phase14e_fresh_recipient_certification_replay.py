from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_fresh_recipient_certification_evidence_replay_pack import (
    READY,
    REPLAY_STEPS,
    build_fresh_recipient_replay_pack,
    validate_fresh_recipient_replay_pack,
    write_replay_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_replay_pack_is_ready_not_certified() -> None:
    pack = build_fresh_recipient_replay_pack()
    assert pack["status"] == READY
    assert pack["factory_does_not_self_certify"] is True
    assert pack["certification_ready_not_certified"] is True
    assert pack["official_certification_claimed"] is False
    assert validate_fresh_recipient_replay_pack(pack) == []


def test_replay_pack_contains_required_steps() -> None:
    pack = build_fresh_recipient_replay_pack()
    steps_value = pack["replay_steps"]
    assert isinstance(steps_value, list)
    step_ids: set[str] = set()
    for step in steps_value:
        assert isinstance(step, dict)
        step_id = step["step_id"]
        assert isinstance(step_id, str)
        step_ids.add(step_id)
    assert step_ids == set(REPLAY_STEPS)


def test_replay_pack_lists_certification_boundary() -> None:
    pack = build_fresh_recipient_replay_pack()
    boundary_value = pack["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_replay_pack_does_not_execute_release_or_external_actions() -> None:
    pack = build_fresh_recipient_replay_pack()
    assert pack["release_execution_performed"] is False
    assert pack["auto_merge_performed"] is False
    assert pack["auto_tag_performed"] is False
    assert pack["auto_release_performed"] is False
    assert pack["live_provider_calls_performed"] is False
    assert pack["external_system_calls_performed"] is False


def test_replay_pack_references_phase14d_ready_status() -> None:
    pack = build_fresh_recipient_replay_pack()
    assert pack["supporting_evidence_pack_status"] == "CERTIFICATION_READY_RELEASE_CANDIDATE_EVIDENCE_PACK_READY"


def test_replay_pack_report_is_written(tmp_path: Path) -> None:
    pack = build_fresh_recipient_replay_pack()
    output = tmp_path / "fresh_recipient_replay_pack.json"
    write_replay_pack(pack, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-recipient-certification-evidence-replay-pack.v1"
    assert payload["status"] == READY


def test_phase14e_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14e_fresh_recipient_certification_replay.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14E fresh-recipient certification evidence replay artifacts validated." in result.stdout


def test_fresh_recipient_replay_pack_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_fresh_recipient_certification_evidence_replay_pack.py",
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
