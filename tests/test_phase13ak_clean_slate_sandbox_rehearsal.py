from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.rehearse_clean_slate_regeneration_sandbox import (
    SANDBOX_RELATIVE_ROOT,
    build_sandbox_rehearsal_report,
    sample_approval_token_payload,
    validate_sandbox_rehearsal_report,
    write_sandbox_rehearsal_report,
)


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_sandbox_rehearsal_without_token_is_blocked_but_safe() -> None:
    report = build_sandbox_rehearsal_report(Path.cwd())

    assert report.ready is False
    assert report.sandbox_status == "SANDBOX_REHEARSAL_BLOCKED"
    assert report.real_generated_application_deleted is False
    assert report.real_generated_application_overwritten is False
    assert validate_sandbox_rehearsal_report(report) == []


def test_sandbox_rehearsal_with_valid_token_is_ready() -> None:
    token_path = write_token(Path.cwd() / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase13ak")

    report = build_sandbox_rehearsal_report(Path.cwd(), token_path)

    assert report.ready is True
    assert report.sandbox_status == "SANDBOX_REHEARSAL_READY"
    assert report.sandbox_only is True
    assert len(report.manifest_digest) == 64
    token_path.unlink(missing_ok=True)


def test_unapproved_sandbox_root_is_blocked(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_sandbox_rehearsal_report(
        Path.cwd(),
        token_path,
        sandbox_root=Path("workspace/factory_generated/upi_dispute_resolution/generated_application"),
    )

    assert report.ready is False
    assert report.sandbox_only is False


def test_materialize_sandbox_writes_only_under_sandbox(tmp_path: Path) -> None:
    project_root = tmp_path
    token_path = write_token(tmp_path)

    report = build_sandbox_rehearsal_report(
        project_root,
        token_path,
        materialize_sandbox=True,
    )

    assert report.materialized_sandbox is True
    sandbox = project_root / SANDBOX_RELATIVE_ROOT
    assert (sandbox / "README.md").exists()
    assert (sandbox / "manifest" / "rehearsal_scope.json").exists()
    assert not (project_root / "workspace/factory_generated/upi_dispute_resolution/generated_application/README.md").exists()


def test_sandbox_rehearsal_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    report = build_sandbox_rehearsal_report(Path.cwd(), token_path)
    output = tmp_path / "sandbox_rehearsal.json"

    write_sandbox_rehearsal_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "clean-slate-sandbox-rehearsal-report.v1"
    assert payload["real_generated_application_deleted"] is False
    assert payload["real_generated_application_overwritten"] is False


def test_sandbox_rehearsal_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/rehearse_clean_slate_regeneration_sandbox.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["sandbox_status"] == "SANDBOX_REHEARSAL_BLOCKED"


def test_sandbox_rehearsal_cli_with_valid_token_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rehearse_clean_slate_regeneration_sandbox.py",
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
    assert payload["sandbox_status"] == "SANDBOX_REHEARSAL_READY"
    assert payload["ready"] is True


def test_phase13ak_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ak_clean_slate_sandbox_rehearsal.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AK clean-slate sandbox rehearsal artifacts validated." in result.stdout
