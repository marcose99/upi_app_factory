from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.apply_governed_low_risk_repair import (
    STATUS_APPLIED,
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    LowRiskRepairRequest,
    apply_low_risk_repair,
    validate_low_risk_repair_result,
    write_low_risk_repair_result,
)


def write_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_doc_repair_dry_run_is_ready_and_does_not_mutate(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/example.md", "old phrase\n")

    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("docs/example.md"),
            repair_class="REPAIR-DOC-001",
            old_text="old phrase",
            new_text="new phrase",
            apply=False,
            sandbox_acknowledged=False,
        )
    )

    assert result.repair_status == STATUS_DRY_RUN
    assert result.dry_run is True
    assert result.applied is False
    assert (tmp_path / "docs/example.md").read_text(encoding="utf-8") == "old phrase\n"
    assert validate_low_risk_repair_result(result) == []


def test_doc_repair_applies_in_acknowledged_sandbox(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/example.md", "old phrase\n")

    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("docs/example.md"),
            repair_class="REPAIR-DOC-001",
            old_text="old phrase",
            new_text="new phrase",
            apply=True,
            sandbox_acknowledged=True,
        )
    )

    assert result.repair_status == STATUS_APPLIED
    assert result.applied is True
    assert "new phrase" in (tmp_path / "docs/example.md").read_text(encoding="utf-8")
    assert result.backup_snapshot == "old phrase\n"


def test_apply_without_sandbox_acknowledgement_is_blocked(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/example.md", "old phrase\n")

    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("docs/example.md"),
            repair_class="REPAIR-DOC-001",
            old_text="old phrase",
            new_text="new phrase",
            apply=True,
            sandbox_acknowledged=False,
        )
    )

    assert result.repair_status == STATUS_BLOCKED
    assert "old phrase" in (tmp_path / "docs/example.md").read_text(encoding="utf-8")


def test_protected_generated_application_path_is_blocked(tmp_path: Path) -> None:
    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("workspace/factory_generated/upi_dispute_resolution/generated_application/file.md"),
            repair_class="REPAIR-DOC-001",
            old_text="x",
            new_text="y",
            apply=True,
            sandbox_acknowledged=True,
        )
    )

    assert result.repair_status == STATUS_BLOCKED
    assert result.real_generated_application_deleted is False
    assert result.real_generated_application_overwritten is False


def test_unsupported_repair_class_is_blocked(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/example.md", "old phrase\n")

    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("docs/example.md"),
            repair_class="REPAIR-UNSAFE-999",
            old_text="old phrase",
            new_text="new phrase",
            apply=True,
            sandbox_acknowledged=True,
        )
    )

    assert result.repair_status == STATUS_BLOCKED


def test_python_typing_repair_applies_to_python_file(tmp_path: Path) -> None:
    write_file(tmp_path, "scripts/example.py", "items = ()\n")

    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("scripts/example.py"),
            repair_class="REPAIR-TYPE-001",
            old_text="items = ()",
            new_text="items: tuple[str, ...] = ()",
            apply=True,
            sandbox_acknowledged=True,
        )
    )

    assert result.repair_status == STATUS_APPLIED
    assert "tuple[str, ...]" in (tmp_path / "scripts/example.py").read_text(encoding="utf-8")


def test_terminology_repair_applies_to_markdown_file(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/example.md", "application generation boundary\n")

    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("docs/example.md"),
            repair_class="REPAIR-TERM-001",
            old_text="application generation",
            new_text="application engineering",
            apply=True,
            sandbox_acknowledged=True,
        )
    )

    assert result.repair_status == STATUS_APPLIED
    assert "application engineering" in (tmp_path / "docs/example.md").read_text(encoding="utf-8")


def test_low_risk_repair_audit_report_is_written(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/example.md", "old phrase\n")
    result = apply_low_risk_repair(
        LowRiskRepairRequest(
            target_root=tmp_path,
            relative_path=Path("docs/example.md"),
            repair_class="REPAIR-DOC-001",
            old_text="old phrase",
            new_text="new phrase",
            apply=True,
            sandbox_acknowledged=True,
        )
    )
    output = tmp_path / "repair_result.json"

    write_low_risk_repair_result(result, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "low-risk-autonomous-repair-result.v1"
    assert payload["repair_status"] == STATUS_APPLIED
    assert payload["factory_self_modification_applied"] is False


def test_low_risk_repair_cli_applies_in_acknowledged_sandbox(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/cli.md", "alpha\n")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/apply_governed_low_risk_repair.py",
            "--target-root",
            str(tmp_path),
            "--relative-path",
            "docs/cli.md",
            "--repair-class",
            "REPAIR-DOC-001",
            "--old-text",
            "alpha",
            "--new-text",
            "beta",
            "--apply",
            "--sandbox-acknowledged",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["repair_status"] == STATUS_APPLIED
    assert "beta" in (tmp_path / "docs/cli.md").read_text(encoding="utf-8")


def test_phase13au_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13au_low_risk_repair_applier.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AU governed low-risk autonomous repair applier artifacts validated." in result.stdout
