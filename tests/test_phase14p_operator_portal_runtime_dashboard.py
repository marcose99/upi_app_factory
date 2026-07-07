from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_runtime_dashboard_proof import (
    OPERATOR_VISIBLE_WORDING,
    READY,
    RUNTIME_ROUTES,
    build_operator_portal_runtime_dashboard_proof,
    validate_operator_portal_runtime_dashboard_proof,
    write_runtime_dashboard_proof,
)


AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14p/operator_portal_runtime_dashboard_audit.json"
)


def test_runtime_dashboard_plan_is_ready_and_not_certified() -> None:
    proof = build_operator_portal_runtime_dashboard_proof(execute_probe=False)
    assert proof["status"] == READY
    assert proof["portal_runtime_probe_performed"] is False
    assert proof["external_ecosystem_integrations_remain_mock"] is True
    assert proof["factory_does_not_self_certify"] is True
    assert proof["certification_ready_not_certified"] is True
    assert proof["official_certification_claimed"] is False
    assert proof["official_certification_granted_by_factory"] is False
    assert validate_operator_portal_runtime_dashboard_proof(proof) == []


def test_executed_runtime_dashboard_audit_is_present() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["status"] == READY
    assert audit["portal_runtime_probe_performed"] is True
    assert validate_operator_portal_runtime_dashboard_proof(audit, require_executed=True) == []


def test_runtime_dashboard_routes_are_probed() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    routes_value = audit["runtime_routes"]
    probe_results = audit["runtime_probe_results"]
    assert isinstance(routes_value, list)
    assert isinstance(probe_results, list)
    assert set(routes_value) == set(RUNTIME_ROUTES)
    probed_routes = {result["route"] for result in probe_results}
    assert probed_routes == set(RUNTIME_ROUTES)


def test_runtime_dashboard_responses_are_successful_and_operator_visible() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    probe_results = audit["runtime_probe_results"]
    assert isinstance(probe_results, list)
    for result in probe_results:
        assert result["status_code"] == 200
        assert result["contains_required_wording"] is True


def test_runtime_dashboard_operator_wording_is_preserved() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    wording_value = audit["operator_visible_wording"]
    assert isinstance(wording_value, list)
    assert set(wording_value) == set(OPERATOR_VISIBLE_WORDING)


def test_runtime_dashboard_preserves_certification_boundary() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    boundary_value = audit["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_runtime_dashboard_preserves_human_gates() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["human_approval_required_for_release_candidate_declaration"] is True
    assert audit["human_approval_required_for_promotion"] is True
    assert audit["human_approval_required_for_merge"] is True
    assert audit["human_approval_required_for_tag"] is True
    assert audit["human_approval_required_for_release"] is True


def test_runtime_dashboard_does_not_release_or_call_external_systems() -> None:
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


def test_runtime_dashboard_report_is_written(tmp_path: Path) -> None:
    proof = build_operator_portal_runtime_dashboard_proof(execute_probe=False)
    output = tmp_path / "operator_portal_runtime_dashboard_proof.json"
    write_runtime_dashboard_proof(proof, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "operator-portal-runtime-dashboard-proof.v1"
    assert payload["status"] == READY


def test_phase14p_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14p_operator_portal_runtime_dashboard.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14P operator portal runtime dashboard proof artifacts validated." in result.stdout


def test_runtime_dashboard_cli_plan_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_operator_portal_runtime_dashboard_proof.py",
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
