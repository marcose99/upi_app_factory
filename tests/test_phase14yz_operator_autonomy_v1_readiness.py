from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs/phase14y_z/operator_autonomy_dashboard_v1_readiness_pack.md"
POLICY_PATH = PROJECT_ROOT / "policies/phase14yz_operator_autonomy_v1_readiness_policy.json"
VALIDATOR = PROJECT_ROOT / "scripts/validate_phase14yz_operator_autonomy_v1_readiness.py"
RUNNER = PROJECT_ROOT / "scripts/run_operator_autonomy_dashboard_v1_readiness_pack.py"
TRACKED_AUDIT = PROJECT_ROOT / (
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14y_z/operator_autonomy_dashboard_v1_readiness_pack_audit.json"
)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=True)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


def test_phase14yz_validator_passes() -> None:
    completed = run_command([sys.executable, str(VALIDATOR)])
    assert "Phase 14Y-Z operator autonomy dashboard" in completed.stdout


def test_phase14yz_policy_preserves_human_gated_boundaries() -> None:
    policy = load_json(POLICY_PATH)
    assert policy["phase"] == "14Y-Z"
    assert policy["validators_must_be_read_only"] is True
    assert policy["tests_must_use_temporary_audit_outputs"] is True
    assert policy["factory_must_not_self_certify"] is True
    assert "official_certification_claims" in policy["human_gated_actions"]
    assert "auto_certify" in policy["blocked_autonomous_actions"]


def test_phase14yz_document_locks_stable_endgame_rule() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    assert "Stable endgame runner rule" in doc
    assert "Validators are read-only" in doc
    assert "Tests use temporary audit outputs" in doc
    assert "Full regression starts only from a clean committed tree" in doc
    assert "certifying authority review" in doc


def test_phase14yz_runner_writes_temporary_audit_without_tracked_target(tmp_path: Path) -> None:
    audit_out = tmp_path / "phase14yz_audit.json"
    completed = run_command([sys.executable, str(RUNNER), "--audit-out", str(audit_out)])
    assert "OPERATOR_AUTONOMY_DASHBOARD_V1_READINESS_PACK_READY" in completed.stdout
    audit = load_json(audit_out)
    assert audit["phase"] == "14Y-Z"
    assert audit["operator_autonomy_dashboard_enabled"] is True
    assert audit["v1_autonomous_readiness_pack_enabled"] is True
    assert audit["tests_use_temporary_audit_outputs"] is True
    assert audit["official_certification_granted_by_factory"] is False
    assert TRACKED_AUDIT.exists()


def test_phase14yz_audit_contains_dashboard_and_readiness_sections() -> None:
    audit = load_json(TRACKED_AUDIT)
    assert "quality_gate_matrix" in audit["operator_dashboard_sections"]
    assert "human_approval_queue" in audit["operator_dashboard_sections"]
    assert "local_checkout_replay_readiness" in audit["v1_readiness_pack_sections"]
    assert "official_certification_authority_dependency" in audit["v1_readiness_pack_sections"]
    assert audit["v1_readiness_assessment"]["phase14_endgame_sequence_complete_after_this_phase"] is True


def test_phase14yz_certification_boundary_is_explicit() -> None:
    audit = load_json(TRACKED_AUDIT)
    boundary = audit["what_sits_between_generated_application_and_certification"]
    assert "certifying_authority_review" in boundary
    assert "independent_verification" in boundary
    assert "official_certification_decision" in boundary
    assert audit["factory_does_not_self_certify"] is True
    assert audit["official_certification_claimed"] is False
