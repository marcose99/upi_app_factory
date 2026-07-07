from __future__ import annotations

import subprocess
import sys
from typing import cast

from scripts.run_governed_autonomous_continuation import (
    BLOCKED_AUTONOMOUS_ACTIONS,
    HUMAN_GATED_ACTIONS,
    build_multi_phase_autonomous_continuation_runner,
    read_only_gate_specs,
    validate_multi_phase_autonomous_continuation_runner,
)


def test_phase14s_plan_is_ready_and_governed() -> None:
    audit = build_multi_phase_autonomous_continuation_runner(execute_gates=False)
    assert audit["status"] == "MULTI_PHASE_AUTONOMOUS_CONTINUATION_RUNNER_READY"
    assert audit["multi_phase_autonomous_continuation_enabled"] is True
    assert audit["governed_self_evolution_enabled"] is True
    assert audit["manual_command_reduction_goal"] is True
    assert audit["parallel_execution_limited_to_readonly_gates"] is True
    assert audit["sequential_human_gates_preserved"] is True
    assert validate_multi_phase_autonomous_continuation_runner(audit) == []


def test_phase14s_blocks_irreversible_autonomous_actions() -> None:
    audit = build_multi_phase_autonomous_continuation_runner(execute_gates=False)
    for action in BLOCKED_AUTONOMOUS_ACTIONS:
        assert action in audit["blocked_autonomous_actions"]
    for field in (
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_push_performed",
        "auto_release_performed",
        "auto_promotion_performed",
        "auto_certification_performed",
        "live_provider_calls_performed",
        "destructive_cleanup_performed",
        "external_system_mutation_performed",
    ):
        assert audit[field] is False


def test_phase14s_preserves_human_approval_boundaries() -> None:
    audit = build_multi_phase_autonomous_continuation_runner(execute_gates=False)
    for action in HUMAN_GATED_ACTIONS:
        assert action in audit["human_gated_actions"]
    for field in (
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_push",
        "human_approval_required_for_release",
        "human_approval_required_for_promotion",
        "human_approval_required_for_live_provider_calls",
        "human_approval_required_for_certification_claims",
    ):
        assert audit[field] is True


def test_phase14s_readonly_gates_are_parallel_safe() -> None:
    specs = read_only_gate_specs()
    assert specs
    for spec in specs:
        assert spec["read_only"] is True
        assert spec["parallel_safe"] is True
        command = cast(list[str], spec["command"])
        assert command[0] == sys.executable


def test_phase14s_has_multi_phase_plan_and_safe_repair_catalog() -> None:
    audit = build_multi_phase_autonomous_continuation_runner(execute_gates=False)
    planned = cast(list[str], audit["planned_phase_sequence"])
    repairs = cast(list[str], audit["safe_repair_classes_known"])
    assert len(planned) >= 3
    assert "phase14t/autonomous-safe-repair-catalog-operator-loop" in planned
    assert "mypy_validator_json_object_cast" in repairs
    assert "ruff_e402_import_order_cleanup" in repairs
    assert "ruff_unused_import_cleanup" in repairs


def test_phase14s_cli_plan_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_governed_autonomous_continuation.py",
            "--from-phase",
            "phase14s",
            "--to-phase",
            "phase14z",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase14s_validator_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14s_multi_phase_autonomous_continuation.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
