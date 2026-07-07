from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload
from scripts.run_autonomous_phase_engineering import (
    BLOCKED,
    READY,
    build_autonomous_phase_engineering_run,
    validate_autonomous_phase_engineering_run,
    write_autonomous_phase_engineering_run,
)


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_autonomous_runner_without_token_is_blocked_and_safe() -> None:
    run = build_autonomous_phase_engineering_run(Path.cwd())

    assert run.ready is False
    assert run.runner_status == BLOCKED
    assert run.real_generated_application_deleted is False
    assert run.real_generated_application_overwritten is False
    assert run.factory_self_healing_repair_applied is False
    assert run.factory_self_modification_applied is False
    assert validate_autonomous_phase_engineering_run(run) == []


def test_autonomous_runner_with_token_and_confirmation_is_ready(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    run = build_autonomous_phase_engineering_run(Path.cwd(), token_path, operator_confirmation=True)

    assert run.ready is True
    assert run.runner_status == READY
    assert run.standards_matrix_ready is True


def test_autonomous_runner_creates_blueprints_for_planned_controls(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    run = build_autonomous_phase_engineering_run(Path.cwd(), token_path, operator_confirmation=True)

    assert run.blueprints
    assert len(run.blueprints) >= 5
    assert all(blueprint.future_phase_id.startswith("13") for blueprint in run.blueprints)


def test_blueprints_are_non_destructive_and_human_gated(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    run = build_autonomous_phase_engineering_run(Path.cwd(), token_path, operator_confirmation=True)

    assert all(not blueprint.auto_apply_allowed for blueprint in run.blueprints)
    assert all("auto_merge" in blueprint.blocked_actions for blueprint in run.blueprints)
    assert all("auto_tag" in blueprint.blocked_actions for blueprint in run.blueprints)
    assert all("auto_release" in blueprint.blocked_actions for blueprint in run.blueprints)
    assert all("human approval" in blueprint.human_approval_boundary.lower() for blueprint in run.blueprints)


def test_blueprints_have_artifact_validator_test_and_evidence_plans(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    run = build_autonomous_phase_engineering_run(Path.cwd(), token_path, operator_confirmation=True)

    assert all(blueprint.artifact_plan for blueprint in run.blueprints)
    assert all(blueprint.validator_plan for blueprint in run.blueprints)
    assert all(blueprint.test_plan for blueprint in run.blueprints)
    assert all(blueprint.evidence_plan for blueprint in run.blueprints)
    assert all(blueprint.self_healing_linkage.startswith("REPAIR-") for blueprint in run.blueprints)


def test_autonomous_runner_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    run = build_autonomous_phase_engineering_run(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "autonomous_runner.json"

    write_autonomous_phase_engineering_run(run, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "autonomous-phase-engineering-run.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["factory_self_healing_repair_applied"] is False
    assert payload["factory_self_modification_applied"] is False


def test_autonomous_runner_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_autonomous_phase_engineering.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ready"] is False


def test_autonomous_runner_cli_with_token_and_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_autonomous_phase_engineering.py",
            "--project-root",
            str(Path.cwd()),
            "--approval-token",
            str(token_path),
            "--operator-confirms-final-human-approval",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["runner_status"] == READY
    assert payload["ready"] is True


def test_phase13at_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13at_autonomous_runner.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AT autonomous phase engineering runner artifacts validated." in result.stdout
