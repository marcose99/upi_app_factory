from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.run_governed_autonomous_phase_execution_loop import (
    CANDIDATE_NEXT_PHASES,
    EXECUTION_LOOP_STAGES,
    HUMAN_GATED_ACTIONS,
    READY,
    VALIDATION_GATES,
    build_governed_autonomous_phase_execution_loop,
    validate_governed_autonomous_phase_execution_loop,
    write_execution_loop,
)


def test_execution_loop_is_ready_and_governed() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    assert loop["status"] == READY
    assert loop["autonomous_execution_allowed_inside_governed_branch"] is True
    assert loop["low_risk_self_healing_allowed"] is True
    assert loop["self_evolution_allowed_for_docs_policies_tests_evidence"] is True
    assert validate_governed_autonomous_phase_execution_loop(loop) == []


def test_execution_loop_preserves_human_gates() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    assert loop["human_approval_required_for_promotion"] is True
    assert loop["human_approval_required_for_merge"] is True
    assert loop["human_approval_required_for_tag"] is True
    assert loop["human_approval_required_for_release"] is True


def test_execution_loop_lists_stages() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    stages_value = loop["execution_loop_stages"]
    assert isinstance(stages_value, list)
    stage_ids: set[str] = set()
    human_gate_found = False
    for stage in stages_value:
        assert isinstance(stage, dict)
        stage_id = stage["stage_id"]
        assert isinstance(stage_id, str)
        stage_ids.add(stage_id)
        if stage["human_gate_required"] is True:
            human_gate_found = True
    assert stage_ids == set(EXECUTION_LOOP_STAGES)
    assert human_gate_found is True


def test_execution_loop_lists_validation_gates_and_human_gated_actions() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    gates_value = loop["validation_gates"]
    gated_value = loop["human_gated_actions"]
    assert isinstance(gates_value, list)
    assert isinstance(gated_value, list)
    assert set(gates_value) == set(VALIDATION_GATES)
    assert set(gated_value) == set(HUMAN_GATED_ACTIONS)


def test_execution_loop_uses_policy_approved_candidate_phase() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    assert loop["selected_candidate_phase"] in CANDIDATE_NEXT_PHASES


def test_execution_loop_preserves_certification_boundary() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    assert loop["factory_does_not_self_certify"] is True
    assert loop["certification_ready_not_certified"] is True
    assert loop["official_certification_claimed"] is False
    assert loop["official_certification_granted_by_factory"] is False
    boundary_value = loop["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_execution_loop_does_not_release_or_call_external_systems() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    assert loop["release_execution_performed"] is False
    assert loop["auto_merge_performed"] is False
    assert loop["auto_tag_performed"] is False
    assert loop["auto_release_performed"] is False
    assert loop["live_provider_calls_performed"] is False
    assert loop["external_system_calls_performed"] is False
    assert loop["arbitrary_shell_execution_performed"] is False


def test_execution_loop_references_phase14j_ready_status() -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    assert loop["supporting_orchestrator_status"] == "GOVERNED_AUTONOMOUS_SELF_ENGINEERING_ORCHESTRATOR_READY"


def test_execution_loop_report_is_written(tmp_path: Path) -> None:
    loop = build_governed_autonomous_phase_execution_loop()
    output = tmp_path / "governed_autonomous_phase_execution_loop.json"
    write_execution_loop(loop, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "governed-autonomous-phase-execution-loop.v1"
    assert payload["status"] == READY


def test_phase14k_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14k_governed_autonomous_phase_execution.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14K governed autonomous phase execution loop artifacts validated." in result.stdout


def test_execution_loop_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_governed_autonomous_phase_execution_loop.py",
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
