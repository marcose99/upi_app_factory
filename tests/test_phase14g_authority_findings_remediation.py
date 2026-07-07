from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_authority_findings_remediation_loop import (
    FINDING_SEVERITIES,
    FINDING_STATUSES,
    READY,
    REQUIRED_REGISTERS,
    build_authority_findings_remediation_loop,
    validate_authority_findings_remediation_loop,
    write_authority_findings_loop,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_authority_findings_loop_is_ready_not_certified() -> None:
    loop = build_authority_findings_remediation_loop()
    assert loop["status"] == READY
    assert loop["factory_does_not_self_certify"] is True
    assert loop["certification_ready_not_certified"] is True
    assert loop["official_certification_claimed"] is False
    assert loop["official_certification_granted_by_factory"] is False
    assert validate_authority_findings_remediation_loop(loop) == []


def test_authority_findings_loop_contains_required_registers() -> None:
    loop = build_authority_findings_remediation_loop()
    registers_value = loop["registers"]
    assert isinstance(registers_value, dict)
    assert set(registers_value) == set(REQUIRED_REGISTERS)


def test_authority_findings_loop_contains_severities_and_statuses() -> None:
    loop = build_authority_findings_remediation_loop()
    severities_value = loop["finding_severities"]
    statuses_value = loop["finding_statuses"]
    assert isinstance(severities_value, list)
    assert isinstance(statuses_value, list)
    assert set(severities_value) == set(FINDING_SEVERITIES)
    assert set(statuses_value) == set(FINDING_STATUSES)


def test_authority_findings_loop_lists_certification_boundary() -> None:
    loop = build_authority_findings_remediation_loop()
    boundary_value = loop["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_authority_findings_loop_does_not_execute_remediation_or_release() -> None:
    loop = build_authority_findings_remediation_loop()
    assert loop["automatic_remediation_execution_performed"] is False
    assert loop["release_execution_performed"] is False
    assert loop["auto_merge_performed"] is False
    assert loop["auto_tag_performed"] is False
    assert loop["auto_release_performed"] is False
    assert loop["live_provider_calls_performed"] is False
    assert loop["external_system_calls_performed"] is False


def test_authority_findings_loop_references_phase14f_ready_status() -> None:
    loop = build_authority_findings_remediation_loop()
    assert loop["supporting_review_workspace_status"] == "CERTIFYING_AUTHORITY_REVIEW_WORKSPACE_READY"


def test_authority_findings_loop_report_is_written(tmp_path: Path) -> None:
    loop = build_authority_findings_remediation_loop()
    output = tmp_path / "authority_findings_loop.json"
    write_authority_findings_loop(loop, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "authority-findings-remediation-loop.v1"
    assert payload["status"] == READY


def test_phase14g_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14g_authority_findings_remediation.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14G authority findings remediation loop artifacts validated." in result.stdout


def test_authority_findings_loop_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_authority_findings_remediation_loop.py",
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
