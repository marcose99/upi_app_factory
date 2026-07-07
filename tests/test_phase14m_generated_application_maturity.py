from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_generated_application_maturity_sweep import (
    EXPECTED_GENERATED_APP_TESTS,
    GENERATED_APP_ROOT,
    MATURITY_DIMENSIONS,
    READY,
    build_generated_application_maturity_sweep,
    validate_generated_application_maturity_sweep,
    write_maturity_sweep,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


def test_maturity_sweep_is_ready_and_not_certified() -> None:
    sweep = build_generated_application_maturity_sweep()
    assert sweep["status"] == READY
    assert sweep["primary_generated_application_must_be_real_local_app"] is True
    assert sweep["external_ecosystem_integrations_remain_mock"] is True
    assert sweep["factory_does_not_self_certify"] is True
    assert sweep["certification_ready_not_certified"] is True
    assert sweep["official_certification_claimed"] is False
    assert sweep["official_certification_granted_by_factory"] is False
    assert validate_generated_application_maturity_sweep(sweep) == []


def test_maturity_sweep_finds_generated_app_root_and_tests() -> None:
    sweep = build_generated_application_maturity_sweep()
    assert GENERATED_APP_ROOT.exists()
    assert sweep["generated_app_root_exists"] is True
    for test_path in EXPECTED_GENERATED_APP_TESTS:
        assert Path(test_path).exists()
    assert sweep["test_evidence_files_exist"] is True


def test_maturity_sweep_lists_required_dimensions() -> None:
    sweep = build_generated_application_maturity_sweep()
    dimensions_value = sweep["maturity_dimensions"]
    assert isinstance(dimensions_value, list)
    dimension_ids: set[str] = set()
    for dimension in dimensions_value:
        assert isinstance(dimension, dict)
        dimension_id = dimension["dimension_id"]
        assert isinstance(dimension_id, str)
        dimension_ids.add(dimension_id)
    assert dimension_ids == set(MATURITY_DIMENSIONS)


def test_maturity_sweep_preserves_certification_boundary() -> None:
    sweep = build_generated_application_maturity_sweep()
    boundary_value = sweep["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_maturity_sweep_preserves_human_gates() -> None:
    sweep = build_generated_application_maturity_sweep()
    assert sweep["human_approval_required_for_promotion"] is True
    assert sweep["human_approval_required_for_merge"] is True
    assert sweep["human_approval_required_for_tag"] is True
    assert sweep["human_approval_required_for_release"] is True


def test_maturity_sweep_does_not_mutate_release_or_call_external_systems() -> None:
    sweep = build_generated_application_maturity_sweep()
    assert sweep["release_execution_performed"] is False
    assert sweep["auto_merge_performed"] is False
    assert sweep["auto_tag_performed"] is False
    assert sweep["auto_release_performed"] is False
    assert sweep["live_provider_calls_performed"] is False
    assert sweep["external_system_calls_performed"] is False
    assert sweep["arbitrary_shell_execution_performed"] is False


def test_maturity_sweep_references_phase14k_and_phase14l_ready_statuses() -> None:
    sweep = build_generated_application_maturity_sweep()
    assert sweep["supporting_execution_loop_status"] == "GOVERNED_AUTONOMOUS_PHASE_EXECUTION_LOOP_READY"
    assert sweep["supporting_portal_dashboard_status"] == "OPERATOR_PORTAL_CERTIFICATION_READINESS_DASHBOARD_INTEGRATION_READY"


def test_maturity_sweep_report_is_written(tmp_path: Path) -> None:
    sweep = build_generated_application_maturity_sweep()
    output = tmp_path / "generated_application_maturity_sweep.json"
    write_maturity_sweep(sweep, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "generated-application-maturity-sweep.v1"
    assert payload["status"] == READY


def test_phase14m_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14m_generated_application_maturity.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14M generated application maturity artifacts validated." in result.stdout


def test_maturity_sweep_cli_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_generated_application_maturity_sweep.py",
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
