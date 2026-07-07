from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.build_human_approved_application_engineering_command_pack import (
    BLOCKED,
    READY,
    COMMAND_ITEMS,
    build_human_approved_command_pack,
    validate_human_approved_command_pack,
    write_human_approved_command_pack,
)
from scripts.propose_factory_self_engineering_improvements import (
    build_factory_self_engineering_proposal_pack,
    validate_factory_self_engineering_proposal_pack,
)
from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_command_pack_without_token_is_blocked_and_safe() -> None:
    pack = build_human_approved_command_pack(Path.cwd())

    assert pack.ready is False
    assert pack.command_pack_status == BLOCKED
    assert pack.real_generated_application_deleted is False
    assert pack.real_generated_application_overwritten is False
    assert pack.destructive_execution_performed is False
    assert pack.factory_self_modification_applied is False
    assert validate_human_approved_command_pack(pack) == []


def test_command_pack_with_token_and_operator_confirmation_is_ready(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = build_human_approved_command_pack(Path.cwd(), token_path, operator_confirmation=True)

    assert pack.ready is True
    assert pack.command_pack_status == READY
    assert pack.approval_token_present is True
    assert pack.operator_confirmation_present is True


def test_command_pack_has_all_required_items(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    pack = build_human_approved_command_pack(Path.cwd(), token_path, operator_confirmation=True)

    names = {item.name for item in pack.command_items}
    assert names == set(COMMAND_ITEMS)
    assert all(item.satisfied for item in pack.command_items)


def test_factory_self_engineering_proposals_are_safe_and_not_applied() -> None:
    proposal_pack = build_factory_self_engineering_proposal_pack(Path.cwd())

    assert proposal_pack.proposals_only is True
    assert proposal_pack.self_modification_applied is False
    assert proposal_pack.live_provider_calls_performed is False
    assert proposal_pack.external_system_calls_performed is False
    assert validate_factory_self_engineering_proposal_pack(proposal_pack) == []
    assert all(not proposal.automatic_application_allowed for proposal in proposal_pack.proposals)
    assert all(proposal.human_approval_required for proposal in proposal_pack.proposals)


def test_command_pack_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    pack = build_human_approved_command_pack(Path.cwd(), token_path, operator_confirmation=True)
    output = tmp_path / "command_pack.json"

    write_human_approved_command_pack(pack, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "human-approved-application-engineering-command-pack.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["factory_self_modification_applied"] is False


def test_command_pack_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_human_approved_application_engineering_command_pack.py",
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


def test_command_pack_cli_with_token_and_operator_confirmation_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_human_approved_application_engineering_command_pack.py",
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
    assert payload["command_pack_status"] == READY
    assert payload["ready"] is True


def test_self_engineering_cli_emits_proposal_only_pack() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/propose_factory_self_engineering_improvements.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["proposal_mode"] == "PROPOSALS_ONLY"
    assert payload["self_modification_applied"] is False


def test_phase13ap_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ap_command_pack.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AP human-approved command pack and self-engineering proposal artifacts validated." in result.stdout
