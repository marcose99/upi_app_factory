from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_generated_application_deep_quality_capability_sweep import (
    QUALITY_DIMENSIONS,
    READY,
    build_generated_application_deep_quality_capability_sweep,
    validate_generated_application_deep_quality_capability_sweep,
    write_deep_quality_sweep,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from typing import Any, cast


AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14q/generated_application_deep_quality_capability_audit.json"
)


def test_deep_quality_plan_is_ready_and_not_certified() -> None:
    sweep = build_generated_application_deep_quality_capability_sweep(execute_sweep=False)
    assert sweep["status"] == READY
    assert sweep["deep_quality_sweep_executed"] is False
    assert sweep["external_ecosystem_integrations_remain_mock"] is True
    assert sweep["factory_does_not_self_certify"] is True
    assert sweep["certification_ready_not_certified"] is True
    assert sweep["official_certification_claimed"] is False
    assert sweep["official_certification_granted_by_factory"] is False
    assert validate_generated_application_deep_quality_capability_sweep(sweep) == []


def test_executed_deep_quality_audit_is_present() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["status"] == READY
    assert audit["deep_quality_sweep_executed"] is True
    assert validate_generated_application_deep_quality_capability_sweep(audit, require_executed=True) == []


def test_deep_quality_dimensions_are_complete() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    dimensions = audit["quality_dimensions"]
    assert isinstance(dimensions, list)
    dimension_ids = {dimension["dimension_id"] for dimension in dimensions}
    assert dimension_ids == set(QUALITY_DIMENSIONS)
    assert all(dimension["status"] != "FAIL" for dimension in dimensions)


def test_deep_quality_command_results_passed() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    command_results = audit["command_results"]
    assert isinstance(command_results, list)
    assert command_results
    command_ids = {result["command_id"] for result in command_results}
    assert "generated_app_local_tests" in command_ids
    assert "capability_slice_tests" in command_ids
    assert all(result["returncode"] == 0 for result in command_results)


def test_deep_quality_preserves_certification_boundary() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    boundary_value = audit["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_deep_quality_preserves_mock_and_no_certification_boundaries() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["external_ecosystem_integrations_remain_mock"] is True
    assert audit["factory_does_not_self_certify"] is True
    assert audit["certification_ready_not_certified"] is True
    assert audit["official_certification_claimed"] is False
    assert audit["official_certification_granted_by_factory"] is False


def test_deep_quality_does_not_release_or_call_external_systems() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["release_execution_performed"] is False
    assert audit["auto_merge_performed"] is False
    assert audit["auto_tag_performed"] is False
    assert audit["auto_release_performed"] is False
    assert audit["live_provider_calls_performed"] is False
    assert audit["external_system_calls_performed"] is False
    assert audit["arbitrary_shell_execution_performed"] is False
    assert audit["real_generated_application_deleted"] is False
    assert audit["real_generated_application_overwritten"] is False


def test_deep_quality_replay_payload_hygiene() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["banned_live_call_findings"] == []
    assert audit["replay_payload_bytecode_findings"] == []


def test_deep_quality_report_is_written(tmp_path: Path) -> None:
    sweep = build_generated_application_deep_quality_capability_sweep(execute_sweep=False)
    output = tmp_path / "generated_application_deep_quality_capability_sweep.json"
    write_deep_quality_sweep(sweep, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "generated-application-deep-quality-capability-sweep.v1"
    assert payload["status"] == READY


def test_phase14q_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14q_generated_application_deep_quality.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14Q generated application deep quality artifacts validated." in result.stdout


def test_deep_quality_cli_plan_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_generated_application_deep_quality_capability_sweep.py",
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


def test_deep_quality_plan_cleans_transient_runtime_caches() -> None:
    generated_root = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")
    cache_dir = generated_root / "app" / "upi_dispute_app" / "__pycache__"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pyc_file = cache_dir / "transient_phase14q_cache.cpython-310.pyc"
    pyc_file.write_bytes(b"transient runtime cache")

    sweep = build_generated_application_deep_quality_capability_sweep(execute_sweep=False)

    quality_dimensions = cast(list[dict[str, Any]], sweep["quality_dimensions"])
    dimensions = {str(item["dimension_id"]): item for item in quality_dimensions}
    assert sweep["replay_payload_bytecode_findings"] == []
    assert dimensions["replay_payload_hygiene"]["status"] == "PASS"
    assert not pyc_file.exists()
    assert not cache_dir.exists()

