from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_governed_autonomy_control_plane import (
    BLOCKED_ACTIONS,
    DecisionStatus,
    READY,
    build_governed_autonomy_control_plane,
    decide_autonomy_action,
    validate_governed_autonomy_control_plane,
    write_governed_autonomy_control_plane,
)


def test_control_plane_is_ready_and_safe() -> None:
    control_plane = build_governed_autonomy_control_plane()
    assert control_plane["status"] == READY
    assert control_plane["control_plane_only"] is True
    assert control_plane["arbitrary_shell_execution_allowed"] is False
    assert control_plane["auto_merge_allowed"] is False
    assert control_plane["auto_tag_allowed"] is False
    assert control_plane["auto_release_allowed"] is False
    assert validate_governed_autonomy_control_plane(control_plane) == []


def test_blocked_actions_are_complete() -> None:
    control_plane = build_governed_autonomy_control_plane()
    blocked = control_plane["blocked_actions"]
    assert isinstance(blocked, list)
    for action in BLOCKED_ACTIONS:
        assert action in blocked


def test_read_only_action_is_approved_at_level_4() -> None:
    decision = decide_autonomy_action("VIEW_FACTORY_STATUS", 4)
    assert decision.status == DecisionStatus.APPROVED
    assert decision.mutation_allowed_now is False


def test_sandbox_generation_is_approved_but_not_worktree_mutation() -> None:
    decision = decide_autonomy_action("GENERATE_IN_SANDBOX", 4)
    assert decision.status == DecisionStatus.APPROVED
    assert decision.execution_zone == "sandbox"
    assert decision.mutation_allowed_now is False


def test_worktree_promotion_requires_sandbox_evidence_before_approval() -> None:
    decision = decide_autonomy_action("PROMOTE_SANDBOX_TO_WORKTREE", 4)
    assert decision.status == DecisionStatus.SANDBOX_EVIDENCE_REQUIRED


def test_worktree_promotion_requires_human_approval_after_sandbox_evidence() -> None:
    decision = decide_autonomy_action("PROMOTE_SANDBOX_TO_WORKTREE", 4, sandbox_evidence_present=True)
    assert decision.status == DecisionStatus.HUMAN_APPROVAL_REQUIRED


def test_worktree_promotion_can_be_approved_with_human_gate_and_sandbox_evidence() -> None:
    decision = decide_autonomy_action(
        "PROMOTE_SANDBOX_TO_WORKTREE",
        4,
        human_approved=True,
        sandbox_evidence_present=True,
    )
    assert decision.status == DecisionStatus.APPROVED
    assert decision.mutation_allowed_now is True


def test_release_action_is_blocked_below_release_level_even_with_approval() -> None:
    decision = decide_autonomy_action("MERGE_MAIN", 4, human_approved=True, sandbox_evidence_present=True)
    assert decision.status == DecisionStatus.BLOCKED


def test_arbitrary_shell_command_remains_blocked_even_at_level_6() -> None:
    decision = decide_autonomy_action(
        "ARBITRARY_SHELL_COMMAND",
        6,
        human_approved=True,
        sandbox_evidence_present=True,
    )
    assert decision.status == DecisionStatus.BLOCKED
    assert decision.mutation_allowed_now is False


def test_control_plane_audit_report_is_written(tmp_path: Path) -> None:
    control_plane = build_governed_autonomy_control_plane()
    output = tmp_path / "autonomy_control_plane.json"
    write_governed_autonomy_control_plane(control_plane, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "governed-autonomy-control-plane.v1"
    assert payload["status"] == READY


def test_autonomy_control_plane_cli_exits_success() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_governed_autonomy_control_plane.py",
            "--default-autonomy-level",
            "4",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == READY


def test_phase13az_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13az_autonomy_control_plane.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AZ governed A-to-Z autonomy control plane artifacts validated." in result.stdout
