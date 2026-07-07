from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.controlled_real_clean_slate_application_engineering import (
    HARNESS_BLOCKED,
    HARNESS_READY,
    build_controlled_harness_report,
    validate_controlled_harness_report,
    write_controlled_harness_report,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_controlled_harness_without_token_is_blocked_and_safe() -> None:
    report = build_controlled_harness_report(Path.cwd())

    assert report.ready is False
    assert report.harness_status == HARNESS_BLOCKED
    assert report.dry_run_only is True
    assert report.destructive_execution_performed is False
    assert report.real_generated_application_deleted is False
    assert report.real_generated_application_overwritten is False
    assert validate_controlled_harness_report(report) == []


def test_controlled_harness_with_token_requires_operator_confirmation(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_controlled_harness_report(Path.cwd(), token_path)

    assert report.ready is False
    assert report.harness_status == HARNESS_BLOCKED
    assert report.approval_token_present is True
    assert report.operator_confirmation_present is False


def test_controlled_harness_with_token_and_operator_confirmation_is_ready_dry_run_only(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_controlled_harness_report(Path.cwd(), token_path, operator_confirmation=True)

    assert report.ready is True
    assert report.harness_status == HARNESS_READY
    assert report.dry_run_only is True
    assert report.future_destructive_phase_required is True


def test_controlled_harness_plans_required_sequence(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    report = build_controlled_harness_report(Path.cwd(), token_path, operator_confirmation=True)

    names = {step.name for step in report.planned_steps}

    assert "capture_pre_state" in names
    assert "plan_delete_real_generated_application" in names
    assert "plan_engineer_application_from_requirement_package" in names
    assert "plan_full_post_engineering_certification" in names
    assert "plan_human_merge_tag_release_gate" in names


def test_controlled_harness_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    report = build_controlled_harness_report(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "controlled_harness.json"

    write_controlled_harness_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "controlled-real-clean-slate-application-engineering-report.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["destructive_execution_performed"] is False


def test_controlled_harness_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/controlled_real_clean_slate_application_engineering.py",
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


def test_controlled_harness_cli_with_token_and_operator_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/controlled_real_clean_slate_application_engineering.py",
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
    assert payload["harness_status"] == HARNESS_READY
    assert payload["ready"] is True
    assert payload["dry_run_only"] is True


def test_phase13an_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13an_controlled_harness.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AN controlled real clean-slate application engineering harness artifacts validated." in result.stdout
