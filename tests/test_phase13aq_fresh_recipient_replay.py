from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.build_fresh_recipient_handover_replay_pack import (
    BLOCKED,
    READY,
    REPLAY_ITEMS,
    build_fresh_recipient_replay_pack,
    validate_fresh_recipient_replay_pack,
    write_fresh_recipient_replay_pack,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_fresh_recipient_replay_without_token_is_blocked_and_safe() -> None:
    pack = build_fresh_recipient_replay_pack(Path.cwd())

    assert pack.ready is False
    assert pack.replay_status == BLOCKED
    assert pack.real_generated_application_deleted is False
    assert pack.real_generated_application_overwritten is False
    assert pack.destructive_execution_performed is False
    assert pack.factory_self_healing_repair_applied is False
    assert pack.factory_self_modification_applied is False
    assert validate_fresh_recipient_replay_pack(pack) == []


def test_fresh_recipient_replay_with_token_and_operator_confirmation_is_ready(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = build_fresh_recipient_replay_pack(Path.cwd(), token_path, operator_confirmation=True)

    assert pack.ready is True
    assert pack.replay_status == READY
    assert pack.command_pack_ready is True


def test_fresh_recipient_replay_has_all_required_items(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = build_fresh_recipient_replay_pack(Path.cwd(), token_path, operator_confirmation=True)

    names = {item.name for item in pack.replay_items}
    assert names == set(REPLAY_ITEMS)
    assert all(item.satisfied for item in pack.replay_items)


def test_self_healing_diagnostics_are_proposal_only(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = build_fresh_recipient_replay_pack(Path.cwd(), token_path, operator_confirmation=True)

    assert pack.self_healing_diagnostics
    assert all(not diagnostic.auto_apply_allowed for diagnostic in pack.self_healing_diagnostics)
    assert all(diagnostic.human_approval_required for diagnostic in pack.self_healing_diagnostics)
    assert all(diagnostic.rollback_required for diagnostic in pack.self_healing_diagnostics)


def test_recipient_commands_include_validation_gates(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = build_fresh_recipient_replay_pack(Path.cwd(), token_path, operator_confirmation=True)
    commands = "\n".join(pack.recommended_recipient_commands)

    assert "validate_phase13ap_command_pack.py" in commands
    assert "validate_phase13aq_fresh_recipient_replay.py" in commands
    assert "python -m ruff check ." in commands
    assert "python -m mypy ." in commands
    assert "python -m pytest" in commands


def test_fresh_recipient_replay_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    pack = build_fresh_recipient_replay_pack(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "fresh_recipient_replay.json"

    write_fresh_recipient_replay_pack(pack, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fresh-recipient-handover-replay-pack.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["factory_self_healing_repair_applied"] is False
    assert payload["factory_self_modification_applied"] is False


def test_fresh_recipient_replay_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_fresh_recipient_handover_replay_pack.py",
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


def test_fresh_recipient_replay_cli_with_token_and_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_fresh_recipient_handover_replay_pack.py",
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
    assert payload["replay_status"] == READY
    assert payload["ready"] is True


def test_phase13aq_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13aq_fresh_recipient_replay.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AQ fresh-recipient replay and safe self-healing artifacts validated." in result.stdout
