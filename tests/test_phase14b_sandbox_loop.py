from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_sandbox_autonomous_generation_validation_loop import (
    READY,
    build_sandbox_generated_preview,
    build_sandbox_loop_report,
    validate_sandbox_loop_report,
    write_sandbox_loop_report,
)


def test_sandbox_preview_declares_capabilities_and_mocks() -> None:
    preview = build_sandbox_generated_preview("upi_dispute_resolution.demo")
    assert "case_intake" in preview.capabilities
    assert "sla_escalation" in preview.capabilities
    assert all(boundary.startswith("mock_") for boundary in preview.mock_boundaries)


def test_sandbox_loop_report_is_ready_and_sandbox_only() -> None:
    report = build_sandbox_loop_report()
    assert report["status"] == READY
    assert report["execution_mode"] == "SANDBOX_ONLY"
    assert report["real_command_execution_performed"] is False
    assert validate_sandbox_loop_report(report) == []


def test_sandbox_loop_evidence_blocks_real_mutation() -> None:
    report = build_sandbox_loop_report()
    evidence_value = report["evidence_record"]
    assert isinstance(evidence_value, dict)
    assert evidence_value["sandbox_only"] is True
    assert evidence_value["real_worktree_mutated"] is False
    assert evidence_value["real_generated_application_written"] is False


def test_sandbox_validation_report_passes() -> None:
    report = build_sandbox_loop_report()
    validation_value = report["sandbox_validation_report"]
    assert isinstance(validation_value, dict)
    assert validation_value["status"] == "PASSED"
    assert validation_value["external_integrations_remain_mocked"] is True


def test_promotion_gate_requires_human_approval() -> None:
    report = build_sandbox_loop_report()
    promotion_value = report["promotion_gate_record"]
    assert isinstance(promotion_value, dict)
    assert promotion_value["human_approval_required"] is True
    assert promotion_value["promotion_allowed_now"] is False


def test_sandbox_loop_audit_report_is_written(tmp_path: Path) -> None:
    report = build_sandbox_loop_report()
    output = tmp_path / "sandbox_loop_report.json"
    write_sandbox_loop_report(report, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sandbox-autonomous-generation-validation-report.v1"
    assert payload["status"] == READY


def test_sandbox_loop_cli_exits_success() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sandbox_autonomous_generation_validation_loop.py",
            "--requirement-id",
            "upi_dispute_resolution.demo",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == READY


def test_phase14b_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14b_sandbox_loop.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14B sandbox autonomous generation and validation loop artifacts validated." in result.stdout
