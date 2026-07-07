from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.gate_real_clean_slate_application_engineering import (
    BLOCKED_OPERATOR,
    BLOCKED_SANDBOX,
    READY,
    build_execution_gate_report,
    validate_execution_gate_report,
    write_execution_gate_report,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_execution_gate_without_token_is_blocked_and_safe() -> None:
    report = build_execution_gate_report(Path.cwd())

    assert report.ready is False
    assert report.gate_status == BLOCKED_SANDBOX
    assert report.destructive_execution_enabled is False
    assert report.real_generated_application_deleted is False
    assert report.real_generated_application_overwritten is False
    assert validate_execution_gate_report(report) == []


def test_execution_gate_with_token_requires_operator_confirmation(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_execution_gate_report(Path.cwd(), token_path)

    assert report.ready is False
    assert report.gate_status == BLOCKED_OPERATOR
    assert report.approval_token_present is True
    assert report.operator_confirmation_present is False


def test_execution_gate_with_token_and_operator_confirmation_is_ready_but_non_destructive(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_execution_gate_report(Path.cwd(), token_path, operator_confirmation=True)

    assert report.ready is True
    assert report.gate_status == READY
    assert report.destructive_execution_enabled is False
    assert report.destructive_delete_performed is False
    assert report.future_phase_required is True


def test_execution_gate_records_required_future_gates(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    report = build_execution_gate_report(Path.cwd(), token_path, operator_confirmation=True)

    assert "post_engineering_certification" in report.required_future_gates
    assert "human_merge_tag_release_gate" in report.required_future_gates
    assert "human_approval_token" in report.required_future_gates


def test_execution_gate_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    report = build_execution_gate_report(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "execution_gate.json"

    write_execution_gate_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "real-clean-slate-application-engineering-execution-gate-report.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["destructive_execution_enabled"] is False


def test_execution_gate_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/gate_real_clean_slate_application_engineering.py",
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


def test_execution_gate_cli_with_token_and_operator_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/gate_real_clean_slate_application_engineering.py",
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
    assert payload["gate_status"] == READY
    assert payload["ready"] is True
    assert payload["destructive_execution_enabled"] is False


def test_phase13am_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13am_real_execution_gate.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AM real clean-slate application engineering execution gate artifacts validated." in result.stdout
