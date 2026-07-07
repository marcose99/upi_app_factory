from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_governed_autonomous_self_engineering_orchestrator import (
    ALLOWED_AUTONOMOUS_ACTIONS,
    BLOCKED_ACTIONS,
    ORCHESTRATION_STEPS,
    READY,
    build_governed_autonomous_self_engineering_orchestrator,
    validate_governed_autonomous_self_engineering_orchestrator,
    write_orchestrator,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_orchestrator_is_ready_and_governed() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    assert orchestrator["status"] == READY
    assert orchestrator["governed_autonomous_self_engineering_allowed"] is True
    assert orchestrator["governed_low_risk_self_healing_allowed"] is True
    assert orchestrator["governed_self_evolution_allowed"] is True
    assert validate_governed_autonomous_self_engineering_orchestrator(orchestrator) == []


def test_orchestrator_preserves_human_approval_gates() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    assert orchestrator["human_approval_required_for_promotion"] is True
    assert orchestrator["human_approval_required_for_merge"] is True
    assert orchestrator["human_approval_required_for_tag"] is True
    assert orchestrator["human_approval_required_for_release"] is True


def test_orchestrator_preserves_certification_boundary() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    assert orchestrator["factory_does_not_self_certify"] is True
    assert orchestrator["certification_ready_not_certified"] is True
    assert orchestrator["official_certification_claimed"] is False
    assert orchestrator["official_certification_granted_by_factory"] is False


def test_orchestrator_lists_allowed_and_blocked_actions() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    allowed_value = orchestrator["allowed_autonomous_actions"]
    blocked_value = orchestrator["blocked_actions"]
    assert isinstance(allowed_value, list)
    assert isinstance(blocked_value, list)
    assert set(allowed_value) == set(ALLOWED_AUTONOMOUS_ACTIONS)
    assert set(blocked_value) == set(BLOCKED_ACTIONS)


def test_orchestrator_lists_steps_and_human_gate_stop() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    steps_value = orchestrator["orchestration_steps"]
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
    assert step_ids == set(ORCHESTRATION_STEPS)
    assert human_gate_found is True


def test_orchestrator_lists_certification_boundary() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    boundary_value = orchestrator["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_orchestrator_does_not_release_or_call_external_systems() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    assert orchestrator["release_execution_performed"] is False
    assert orchestrator["auto_merge_performed"] is False
    assert orchestrator["auto_tag_performed"] is False
    assert orchestrator["auto_release_performed"] is False
    assert orchestrator["live_provider_calls_performed"] is False
    assert orchestrator["external_system_calls_performed"] is False
    assert orchestrator["arbitrary_shell_execution_performed"] is False


def test_orchestrator_references_phase14i_ready_status() -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    assert orchestrator["supporting_dashboard_index_status"] == "CERTIFICATION_READINESS_DASHBOARD_INDEX_READY"


def test_orchestrator_report_is_written(tmp_path: Path) -> None:
    orchestrator = build_governed_autonomous_self_engineering_orchestrator()
    output = tmp_path / "governed_autonomous_self_engineering_orchestrator.json"
    write_orchestrator(orchestrator, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "governed-autonomous-self-engineering-orchestrator.v1"
    assert payload["status"] == READY


def test_phase14j_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14j_governed_autonomous_self_engineering.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14J governed autonomous self-engineering artifacts validated." in result.stdout


def test_orchestrator_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_governed_autonomous_self_engineering_orchestrator.py",
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
