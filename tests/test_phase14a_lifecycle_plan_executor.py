from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_autonomous_lifecycle_plan_executor import (
    READY,
    REQUIRED_STEP_IDS,
    build_autonomous_lifecycle_plan,
    validate_autonomous_lifecycle_plan,
    write_autonomous_lifecycle_plan,
)


def test_lifecycle_plan_is_ready_and_plan_only() -> None:
    plan = build_autonomous_lifecycle_plan()
    assert plan["status"] == READY
    assert plan["plan_only"] is True
    assert plan["real_command_execution_performed"] is False
    assert plan["real_worktree_mutated"] is False
    assert validate_autonomous_lifecycle_plan(plan) == []


def test_lifecycle_plan_contains_required_steps() -> None:
    plan = build_autonomous_lifecycle_plan()
    steps = plan["steps"]
    assert isinstance(steps, list)
    assert {step["step_id"] for step in steps} == set(REQUIRED_STEP_IDS)


def test_lifecycle_plan_steps_do_not_enable_execution() -> None:
    plan = build_autonomous_lifecycle_plan()
    steps = plan["steps"]
    assert isinstance(steps, list)
    for step in steps:
        assert step["execution_enabled"] is False


def test_lifecycle_plan_includes_control_plane_decisions() -> None:
    plan = build_autonomous_lifecycle_plan()
    steps = plan["steps"]
    assert isinstance(steps, list)
    statuses = {step["decision"]["status"] for step in steps}
    assert "APPROVED" in statuses
    assert "HUMAN_APPROVAL_REQUIRED" in statuses


def test_worktree_and_release_steps_are_human_gated() -> None:
    plan = build_autonomous_lifecycle_plan()
    steps_value = plan["steps"]
    assert isinstance(steps_value, list)
    steps: dict[str, dict[str, object]] = {}
    for step in steps_value:
        assert isinstance(step, dict)
        step_id = step["step_id"]
        assert isinstance(step_id, str)
        steps[step_id] = step
    assert steps["worktree_promotion_gate"]["human_approval_boundary"] == "human_approval_required"
    assert steps["release_candidate_gate"]["human_approval_boundary"] == "human_approval_required"


def test_lifecycle_plan_audit_report_is_written(tmp_path: Path) -> None:
    plan = build_autonomous_lifecycle_plan()
    output = tmp_path / "lifecycle_plan.json"
    write_autonomous_lifecycle_plan(plan, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "autonomous-lifecycle-plan.v1"
    assert payload["status"] == READY


def test_lifecycle_plan_executor_cli_exits_success() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_autonomous_lifecycle_plan_executor.py",
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


def test_phase14a_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14a_lifecycle_plan_executor.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14A autonomous lifecycle plan executor artifacts validated." in result.stdout
