from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.build_local_industry_standards_control_matrix import (
    BLOCKED,
    READY,
    STANDARD_FAMILIES,
    STATUS_PLANNED,
    STATUS_PRESENT,
    build_local_standards_control_matrix,
    validate_local_standards_control_matrix,
    write_local_standards_control_matrix,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_standards_matrix_without_token_is_blocked_and_safe() -> None:
    matrix = build_local_standards_control_matrix(Path.cwd())

    assert matrix.ready is False
    assert matrix.matrix_status == BLOCKED
    assert matrix.real_generated_application_deleted is False
    assert matrix.real_generated_application_overwritten is False
    assert matrix.factory_self_healing_repair_applied is False
    assert matrix.factory_self_modification_applied is False
    assert validate_local_standards_control_matrix(matrix) == []


def test_standards_matrix_with_token_and_confirmation_is_ready(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    matrix = build_local_standards_control_matrix(Path.cwd(), token_path, operator_confirmation=True)

    assert matrix.ready is True
    assert matrix.matrix_status == READY
    assert matrix.repair_catalog_ready is True


def test_standards_matrix_covers_all_required_families(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    matrix = build_local_standards_control_matrix(Path.cwd(), token_path, operator_confirmation=True)

    families = {control.standard_family for control in matrix.controls}
    assert families == set(STANDARD_FAMILIES)


def test_standards_matrix_has_present_and_planned_controls(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    matrix = build_local_standards_control_matrix(Path.cwd(), token_path, operator_confirmation=True)
    statuses = {control.local_status for control in matrix.controls}

    assert STATUS_PRESENT in statuses
    assert STATUS_PLANNED in statuses
    assert matrix.locally_eliminated_gap_count >= 2
    assert matrix.planned_gap_count >= 5


def test_standards_controls_have_local_replay_and_repair_linkage(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    matrix = build_local_standards_control_matrix(Path.cwd(), token_path, operator_confirmation=True)

    assert all(control.replay_command.startswith("python ") for control in matrix.controls)
    assert all(control.self_healing_linkage.startswith("REPAIR-") for control in matrix.controls)
    assert all(control.policy_ref for control in matrix.controls)
    assert all(control.validator_ref for control in matrix.controls)
    assert all(control.test_ref for control in matrix.controls)
    assert all(control.evidence_ref for control in matrix.controls)


def test_standards_matrix_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    matrix = build_local_standards_control_matrix(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "standards_matrix.json"

    write_local_standards_control_matrix(matrix, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "local-industry-standards-control-matrix.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["factory_self_healing_repair_applied"] is False
    assert payload["factory_self_modification_applied"] is False


def test_standards_matrix_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_local_industry_standards_control_matrix.py",
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


def test_standards_matrix_cli_with_token_and_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_local_industry_standards_control_matrix.py",
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
    assert payload["matrix_status"] == READY
    assert payload["ready"] is True


def test_phase13as_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13as_standards_control_matrix.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AS local industry standards control matrix artifacts validated." in result.stdout
