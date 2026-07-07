from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.assemble_final_clean_slate_application_engineering_readiness_pack import (
    BLOCKED,
    READY,
    READINESS_ITEMS,
    assemble_final_readiness_pack,
    validate_final_readiness_pack,
    write_final_readiness_pack,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_final_readiness_pack_without_token_is_blocked_and_safe() -> None:
    pack = assemble_final_readiness_pack(Path.cwd())

    assert pack.ready is False
    assert pack.readiness_status == BLOCKED
    assert pack.real_generated_application_deleted is False
    assert pack.real_generated_application_overwritten is False
    assert pack.destructive_execution_performed is False
    assert validate_final_readiness_pack(pack) == []


def test_final_readiness_pack_with_token_and_operator_confirmation_is_ready(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = assemble_final_readiness_pack(Path.cwd(), token_path, operator_confirmation=True)

    assert pack.ready is True
    assert pack.readiness_status == READY
    assert pack.ready_for_human_review is True
    assert pack.next_phase_requires_new_human_approval is True


def test_final_readiness_pack_has_all_required_items(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = assemble_final_readiness_pack(Path.cwd(), token_path, operator_confirmation=True)

    names = {item.name for item in pack.readiness_items}
    assert names == set(READINESS_ITEMS)
    assert all(item.satisfied for item in pack.readiness_items)


def test_final_readiness_pack_requires_approval_and_operator_confirmation(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    without_operator = assemble_final_readiness_pack(Path.cwd(), token_path)

    assert without_operator.ready is False
    assert without_operator.operator_confirmation_present is False


def test_final_readiness_pack_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    pack = assemble_final_readiness_pack(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "final_readiness.json"

    write_final_readiness_pack(pack, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "final-clean-slate-application-engineering-readiness-pack.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["destructive_execution_performed"] is False


def test_final_readiness_pack_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/assemble_final_clean_slate_application_engineering_readiness_pack.py",
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


def test_final_readiness_pack_cli_with_token_and_operator_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/assemble_final_clean_slate_application_engineering_readiness_pack.py",
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
    assert payload["readiness_status"] == READY
    assert payload["ready"] is True


def test_phase13ao_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ao_final_readiness_pack.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AO final clean-slate application engineering readiness pack artifacts validated." in result.stdout
