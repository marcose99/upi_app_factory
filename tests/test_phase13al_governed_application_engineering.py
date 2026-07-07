from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.rehearse_clean_slate_regeneration_sandbox import sample_approval_token_payload
from scripts.run_governed_application_engineering_sandbox import (
    ENGINEERING_SANDBOX_RELATIVE_ROOT,
    ENGINEERING_STAGES,
    build_application_engineering_report,
    validate_application_engineering_report,
    write_application_engineering_report,
)


def write_token(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(payload or sample_approval_token_payload(), indent=2), encoding="utf-8")
    return token_path


def test_application_engineering_without_token_is_blocked_but_safe() -> None:
    report = build_application_engineering_report(Path.cwd())

    assert report.ready is False
    assert report.engineering_status == "APPLICATION_ENGINEERING_SANDBOX_BLOCKED"
    assert report.preferred_term == "application engineering"
    assert report.real_generated_application_deleted is False
    assert report.real_generated_application_overwritten is False
    assert validate_application_engineering_report(report) == []


def test_application_engineering_with_valid_token_is_ready() -> None:
    token_path = write_token(Path.cwd() / "workspace" / "factory_generated" / "upi_dispute_resolution" / "lifecycle_artifacts" / "phase13al")

    report = build_application_engineering_report(Path.cwd(), token_path)

    assert report.ready is True
    assert report.engineering_status == "APPLICATION_ENGINEERING_SANDBOX_READY"
    assert report.sandbox_only is True
    assert report.stages == ENGINEERING_STAGES
    assert len(report.manifest_digest) == 64
    token_path.unlink(missing_ok=True)


def test_unapproved_engineering_sandbox_root_is_blocked(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_application_engineering_report(
        Path.cwd(),
        token_path,
        sandbox_root=Path("workspace/factory_generated/upi_dispute_resolution/generated_application"),
    )

    assert report.ready is False
    assert report.sandbox_only is False


def test_materialize_application_engineering_artifacts_only_under_sandbox(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_application_engineering_report(
        tmp_path,
        token_path,
        materialize_sandbox=True,
    )

    assert report.materialized_sandbox is True
    sandbox = tmp_path / ENGINEERING_SANDBOX_RELATIVE_ROOT
    assert (sandbox / "requirements" / "requirement_package.json").exists()
    assert (sandbox / "architecture" / "adr-0001.md").exists()
    assert (sandbox / "app" / "main.py").exists()
    assert not (tmp_path / "workspace/factory_generated/upi_dispute_resolution/generated_application/app/main.py").exists()


def test_application_engineering_report_has_artifact_per_stage(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    report = build_application_engineering_report(Path.cwd(), token_path)

    artifact_stages = {artifact.stage for artifact in report.artifacts}
    assert artifact_stages == set(ENGINEERING_STAGES)


def test_application_engineering_audit_report_is_written(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)
    report = build_application_engineering_report(Path.cwd(), token_path)
    output = tmp_path / "application_engineering.json"

    write_application_engineering_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "governed-autonomous-application-engineering-report.v1"
    assert payload["preferred_term"] == "application engineering"
    assert payload["real_generated_application_deleted"] is False
    assert payload["real_generated_application_overwritten"] is False


def test_application_engineering_cli_without_token_exits_blocked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_governed_application_engineering_sandbox.py",
            "--project-root",
            str(Path.cwd()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["engineering_status"] == "APPLICATION_ENGINEERING_SANDBOX_BLOCKED"


def test_application_engineering_cli_with_valid_token_exits_success(tmp_path: Path) -> None:
    token_path = write_token(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_governed_application_engineering_sandbox.py",
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
    assert payload["engineering_status"] == "APPLICATION_ENGINEERING_SANDBOX_READY"
    assert payload["ready"] is True


def test_phase13al_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13al_governed_application_engineering.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AL governed autonomous application engineering artifacts validated." in result.stdout
