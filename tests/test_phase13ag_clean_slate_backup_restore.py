from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_clean_slate_backup_restore_plan import (
    build_backup_restore_plan,
    manifest_digest,
    validate_backup_restore_plan,
    write_audit_plan,
)


def test_backup_restore_plan_is_non_destructive_for_current_project() -> None:
    plan = build_backup_restore_plan(Path.cwd())

    assert plan.dry_run_only is True
    assert plan.destructive_delete_performed is False
    assert plan.backup_required_before_delete is True
    assert plan.restore_verification_required is True
    assert len(plan.manifest_digest) == 64
    assert validate_backup_restore_plan(plan) == []


def test_manifest_digest_is_deterministic_for_same_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "workspace/factory_generated/upi_dispute_resolution/generated_application"
    source.mkdir(parents=True)
    (source / "app.py").write_text("print('hello')\n", encoding="utf-8")

    plan_one = build_backup_restore_plan(tmp_path)
    plan_two = build_backup_restore_plan(tmp_path)

    assert plan_one.manifest_digest == plan_two.manifest_digest
    assert plan_one.file_count == 1
    assert plan_one.total_bytes > 0


def test_manifest_digest_changes_when_snapshot_changes(tmp_path: Path) -> None:
    source = tmp_path / "workspace/factory_generated/upi_dispute_resolution/generated_application"
    source.mkdir(parents=True)
    target_file = source / "app.py"
    target_file.write_text("print('hello')\n", encoding="utf-8")
    first = build_backup_restore_plan(tmp_path).manifest_digest

    target_file.write_text("print('changed')\n", encoding="utf-8")
    second = build_backup_restore_plan(tmp_path).manifest_digest

    assert first != second


def test_manifest_digest_for_empty_snapshot_is_valid_sha256() -> None:
    digest = manifest_digest(())

    assert len(digest) == 64


def test_audit_plan_written_as_json(tmp_path: Path) -> None:
    source = tmp_path / "workspace/factory_generated/upi_dispute_resolution/generated_application"
    source.mkdir(parents=True)
    (source / "app.py").write_text("print('hello')\n", encoding="utf-8")
    plan = build_backup_restore_plan(tmp_path)
    output = tmp_path / "audit.json"

    write_audit_plan(plan, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "clean-slate-backup-restore-plan.v1"
    assert payload["file_count"] == 1
    assert payload["destructive_delete_performed"] is False


def test_planner_cli_outputs_backup_restore_plan() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_clean_slate_backup_restore_plan.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "clean-slate-backup-restore-plan.v1"
    assert payload["destructive_delete_performed"] is False


def test_phase13ag_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ag_clean_slate_backup_restore.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AG clean-slate backup/restore artifacts validated." in result.stdout
