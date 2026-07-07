from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_v1_release_candidate_replay_gate import (
    EVIDENCE_ARTIFACTS,
    READY,
    REPLAY_GATE_STEPS,
    build_v1_release_candidate_replay_gate,
    validate_v1_release_candidate_replay_gate,
    write_replay_gate,
)


def test_v1_replay_gate_is_ready_and_not_release() -> None:
    gate = build_v1_release_candidate_replay_gate()
    assert gate["status"] == READY
    assert gate["release_candidate_gate_only"] is True
    assert gate["release_execution_performed"] is False
    assert gate["factory_does_not_self_certify"] is True
    assert gate["certification_ready_not_certified"] is True
    assert gate["official_certification_claimed"] is False
    assert gate["official_certification_granted_by_factory"] is False
    assert validate_v1_release_candidate_replay_gate(gate) == []


def test_v1_replay_gate_lists_steps_and_human_gate() -> None:
    gate = build_v1_release_candidate_replay_gate()
    steps_value = gate["replay_gate_steps"]
    assert isinstance(steps_value, list)
    step_ids: set[str] = set()
    human_gate_found = False
    for step in steps_value:
        assert isinstance(step, dict)
        step_id = step["step_id"]
        assert isinstance(step_id, str)
        step_ids.add(step_id)
        if step["human_gate_required"] is True:
            human_gate_found = True
    assert step_ids == set(REPLAY_GATE_STEPS)
    assert human_gate_found is True


def test_v1_replay_gate_evidence_artifacts_exist() -> None:
    gate = build_v1_release_candidate_replay_gate()
    assert gate["evidence_artifacts_exist"] is True
    for artifact_path in EVIDENCE_ARTIFACTS:
        assert Path(artifact_path).exists()


def test_v1_replay_gate_preserves_certification_boundary() -> None:
    gate = build_v1_release_candidate_replay_gate()
    boundary_value = gate["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_v1_replay_gate_preserves_human_gates() -> None:
    gate = build_v1_release_candidate_replay_gate()
    assert gate["human_approval_required_for_release_candidate_declaration"] is True
    assert gate["human_approval_required_for_promotion"] is True
    assert gate["human_approval_required_for_merge"] is True
    assert gate["human_approval_required_for_tag"] is True
    assert gate["human_approval_required_for_release"] is True


def test_v1_replay_gate_does_not_mutate_release_or_call_external_systems() -> None:
    gate = build_v1_release_candidate_replay_gate()
    assert gate["release_execution_performed"] is False
    assert gate["auto_merge_performed"] is False
    assert gate["auto_tag_performed"] is False
    assert gate["auto_release_performed"] is False
    assert gate["live_provider_calls_performed"] is False
    assert gate["external_system_calls_performed"] is False
    assert gate["arbitrary_shell_execution_performed"] is False


def test_v1_replay_gate_references_phase14k_to_phase14m_ready_statuses() -> None:
    gate = build_v1_release_candidate_replay_gate()
    assert gate["supporting_execution_loop_status"] == "GOVERNED_AUTONOMOUS_PHASE_EXECUTION_LOOP_READY"
    assert gate["supporting_portal_dashboard_status"] == "OPERATOR_PORTAL_CERTIFICATION_READINESS_DASHBOARD_INTEGRATION_READY"
    assert gate["supporting_generated_application_maturity_status"] == "GENERATED_APPLICATION_MATURITY_SWEEP_READY"


def test_v1_replay_gate_report_is_written(tmp_path: Path) -> None:
    gate = build_v1_release_candidate_replay_gate()
    output = tmp_path / "v1_release_candidate_replay_gate.json"
    write_replay_gate(gate, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "v1-release-candidate-replay-gate.v1"
    assert payload["status"] == READY


def test_phase14n_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14n_v1_release_candidate_replay_gate.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14N v1 release-candidate replay gate artifacts validated." in result.stdout


def test_v1_replay_gate_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_v1_release_candidate_replay_gate.py",
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
