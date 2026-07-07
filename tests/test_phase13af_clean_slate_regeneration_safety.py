from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.guard_clean_slate_regeneration import (
    DEFAULT_GENERATED_APPLICATION,
    SafetyDecision,
    build_clean_slate_safety_plan,
    validate_plans,
)


def test_default_generated_application_target_is_allowed_as_dry_run_only() -> None:
    plan = build_clean_slate_safety_plan(Path.cwd())

    assert plan.decision == SafetyDecision.ALLOW_DRY_RUN_PLAN.value
    assert plan.dry_run_only is True
    assert plan.destructive_delete_performed is False
    assert plan.human_approval_required_before_delete is True
    assert plan.backup_required is True


def test_docs_target_is_blocked() -> None:
    plan = build_clean_slate_safety_plan(Path.cwd(), Path("docs"))

    assert plan.decision == SafetyDecision.BLOCK.value
    assert any("approved generated_application boundary" in reason for reason in plan.reasons)


def test_project_root_target_is_blocked() -> None:
    plan = build_clean_slate_safety_plan(Path.cwd(), Path("."))

    assert plan.decision == SafetyDecision.BLOCK.value
    assert any("blocked path" in reason for reason in plan.reasons)


def test_external_absolute_path_is_blocked() -> None:
    plan = build_clean_slate_safety_plan(Path.cwd(), Path("/tmp"))

    assert plan.decision == SafetyDecision.BLOCK.value
    assert any("outside the project root" in reason for reason in plan.reasons)


def test_validate_plans_rejects_inconsistent_destructive_plan() -> None:
    plan = build_clean_slate_safety_plan(Path.cwd())

    failures = validate_plans([plan])

    assert failures == []


def test_guard_cli_allows_default_generated_application_dry_run() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/guard_clean_slate_regeneration.py",
            "--project-root",
            str(Path.cwd()),
            "--target",
            str(DEFAULT_GENERATED_APPLICATION),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["decision"] == "ALLOW_DRY_RUN_PLAN"
    assert payload["destructive_delete_performed"] is False


def test_guard_cli_blocks_docs_target() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/guard_clean_slate_regeneration.py",
            "--project-root",
            str(Path.cwd()),
            "--target",
            "docs",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["decision"] == "BLOCK"


def test_phase13af_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13af_clean_slate_regeneration_safety.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AF clean-slate regeneration safety artifacts validated." in result.stdout
