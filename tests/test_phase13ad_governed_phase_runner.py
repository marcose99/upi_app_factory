from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.governed_phase_runner import (
    GateResult,
    build_governed_phase_run_plan,
    classify_gate_result,
    write_audit_plan,
)
from scripts.governed_self_healing import FailureCategory, RepairDecision


def test_passed_gate_has_no_classification() -> None:
    result = GateResult(
        name="mypy",
        command=("python", "-m", "mypy", "."),
        exit_code=0,
        stdout="Success: no issues found",
        stderr="",
    )

    assert classify_gate_result(result) is None


def test_workspace_mypy_failure_is_autonomous_repair_plan() -> None:
    result = GateResult(
        name="mypy",
        command=("python", "-m", "mypy", "."),
        exit_code=1,
        stdout="workspace/generated/foo.py: error: duplicate module named foo",
        stderr="",
    )

    classification = classify_gate_result(result)

    assert classification is not None
    assert classification.category is FailureCategory.MYPY_ACTIVE_SOURCE_SCOPE
    assert classification.decision is RepairDecision.AUTONOMOUS_REPAIR_ALLOWED


def test_live_provider_failure_requires_human_review() -> None:
    result = GateResult(
        name="policy",
        command=("python", "policy_check.py"),
        exit_code=1,
        stdout="repair requires OpenAI API live provider call",
        stderr="",
    )

    plan = build_governed_phase_run_plan("13AD", [result])

    assert plan.requires_human_review is True
    assert plan.may_continue_autonomously is False
    assert plan.human_escalation_count == 1


def test_autonomous_repair_plan_allows_continuation_for_known_local_failure() -> None:
    result = GateResult(
        name="mypy",
        command=("python", "-m", "mypy", "."),
        exit_code=1,
        stdout="workspace/generated/foo.py duplicate module named foo",
        stderr="",
    )

    plan = build_governed_phase_run_plan("13AD", [result])

    assert plan.failed_gate_count == 1
    assert plan.autonomous_repair_count == 1
    assert plan.human_escalation_count == 0
    assert plan.may_continue_autonomously is True


def test_audit_plan_is_deterministic_json(tmp_path: Path) -> None:
    result = GateResult(
        name="mypy",
        command=("python", "-m", "mypy", "."),
        exit_code=1,
        stdout="workspace/generated/foo.py duplicate module named foo",
        stderr="",
    )
    plan = build_governed_phase_run_plan("13AD", [result])
    output_path = tmp_path / "plan.json"

    write_audit_plan(plan, output_path)

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "governed-phase-run-plan.v1"
    assert loaded["phase"] == "13AD"
    assert loaded["autonomous_repair_count"] == 1
    assert loaded["requires_human_review"] is False


def test_phase13ad_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ad_governed_phase_runner.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AD governed phase-runner integration artifacts validated." in result.stdout


def test_governed_phase_runner_cli_outputs_audit_plan() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/governed_phase_runner.py",
            "--phase",
            "13AD",
            "--gate-name",
            "mypy",
            "--failure-text",
            "workspace/generated/foo.py duplicate module named foo",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["phase"] == "13AD"
    assert payload["autonomous_repair_count"] == 1
    assert payload["human_escalation_count"] == 0
