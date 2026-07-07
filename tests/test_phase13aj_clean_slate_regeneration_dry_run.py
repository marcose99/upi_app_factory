from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.plan_clean_slate_regeneration_dry_run import (
    DRY_RUN_BLOCKED,
    DRY_RUN_READY,
    build_clean_slate_dry_run_plan,
    validate_dry_run_plan,
    write_dry_run_plan,
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


def test_dry_run_without_approval_token_is_blocked() -> None:
    plan = build_clean_slate_dry_run_plan(Path.cwd())

    assert plan.dry_run_status == DRY_RUN_BLOCKED
    assert plan.ready is False
    assert plan.destructive_delete_performed is False
    assert plan.regeneration_performed is False
    assert validate_dry_run_plan(plan) == []


def test_dry_run_with_valid_approval_token_is_ready_non_destructive(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())

    plan = build_clean_slate_dry_run_plan(Path.cwd(), token_path)

    assert plan.dry_run_status == DRY_RUN_READY
    assert plan.ready is True
    assert plan.dry_run_only is True
    assert plan.live_provider_calls_performed is False
    assert plan.external_system_calls_performed is False


def test_dry_run_with_wrong_target_token_is_blocked(tmp_path: Path) -> None:
    token = valid_token()
    token["target_path"] = "docs"
    token_path = write_token(tmp_path, token)

    plan = build_clean_slate_dry_run_plan(Path.cwd(), token_path)

    assert plan.ready is False
    assert plan.dry_run_status == DRY_RUN_BLOCKED


def test_dry_run_plan_contains_required_future_steps(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())
    plan = build_clean_slate_dry_run_plan(Path.cwd(), token_path)

    names = {step.name for step in plan.planned_steps}

    assert "plan_generated_application_delete" in names
    assert "plan_regeneration" in names
    assert "plan_post_regeneration_certification" in names
    assert "plan_human_release_gate" in names


def test_dry_run_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())
    plan = build_clean_slate_dry_run_plan(Path.cwd(), token_path)
    output = tmp_path / "dry_run.json"

    write_dry_run_plan(plan, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "clean-slate-regeneration-dry-run-plan.v1"
    assert payload["ready"] is True
    assert payload["destructive_delete_performed"] is False
    assert payload["regeneration_performed"] is False


def test_dry_run_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/plan_clean_slate_regeneration_dry_run.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["dry_run_status"] == DRY_RUN_BLOCKED


def test_dry_run_cli_with_valid_token_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path, valid_token())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/plan_clean_slate_regeneration_dry_run.py",
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
    assert payload["dry_run_status"] == DRY_RUN_READY
    assert payload["ready"] is True


def test_phase13aj_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13aj_clean_slate_regeneration_dry_run.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AJ clean-slate regeneration dry-run artifacts validated." in result.stdout
