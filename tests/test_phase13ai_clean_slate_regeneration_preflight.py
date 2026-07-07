from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.run_clean_slate_regeneration_preflight import (
    BLOCKED_APPROVAL,
    PREFLIGHT_READY,
    build_clean_slate_preflight_report,
    write_preflight_report,
)
from scripts.validate_clean_slate_human_approval import approval_template


def valid_token() -> dict[str, Any]:
    token = approval_template()
    token["approved_by"] = "local-human-operator"
    token["approval_reason"] = "Controlled test token."
    token["approved_at_utc"] = "2099-01-01T00:00:00Z"
    return token


def write_token(tmp_path: Path, payload: dict[str, Any]) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return token_path


def test_preflight_without_approval_token_is_blocked() -> None:
    report = build_clean_slate_preflight_report(Path.cwd())

    assert report.readiness_status == BLOCKED_APPROVAL
    assert report.ready is False
    assert report.destructive_delete_performed is False
    assert report.regeneration_performed is False


def test_preflight_with_valid_approval_token_is_ready_non_destructive(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())

    report = build_clean_slate_preflight_report(Path.cwd(), token_path)

    assert report.readiness_status == PREFLIGHT_READY
    assert report.ready is True
    assert report.dry_run_only is True
    assert report.guard_allowed is True
    assert report.backup_restore_valid is True
    assert report.approval_token_valid is True


def test_preflight_with_wrong_target_token_is_blocked(tmp_path: Path) -> None:
    token = valid_token()
    token["target_path"] = "docs"
    token_path = write_token(tmp_path, token)

    report = build_clean_slate_preflight_report(Path.cwd(), token_path)

    assert report.ready is False
    assert report.approval_token_valid is False
    assert report.readiness_status == BLOCKED_APPROVAL


def test_preflight_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())
    report = build_clean_slate_preflight_report(Path.cwd(), token_path)
    output = tmp_path / "preflight.json"

    write_preflight_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "clean-slate-regeneration-preflight-report.v1"
    assert payload["ready"] is True
    assert payload["destructive_delete_performed"] is False
    assert payload["regeneration_performed"] is False


def test_preflight_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_clean_slate_regeneration_preflight.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["readiness_status"] == BLOCKED_APPROVAL


def test_preflight_cli_with_valid_token_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_clean_slate_regeneration_preflight.py",
            "--project-root",
            str(Path.cwd()),
            "--approval-token",
            str(token_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["readiness_status"] == PREFLIGHT_READY
    assert payload["ready"] is True


def test_phase13ai_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ai_clean_slate_regeneration_preflight.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AI clean-slate regeneration preflight artifacts validated." in result.stdout
