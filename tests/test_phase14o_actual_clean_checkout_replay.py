from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_actual_clean_checkout_v1_replay_proof import (
    DEFAULT_CHECKOUT_REF,
    READY,
    REPLAY_STEPS,
    build_actual_clean_checkout_v1_replay_proof,
    validate_actual_clean_checkout_v1_replay_proof,
    write_replay_proof,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14o/actual_clean_checkout_v1_replay_audit.json"
)


def test_replay_proof_plan_is_ready_and_not_certified() -> None:
    proof = build_actual_clean_checkout_v1_replay_proof(
        source_root=Path.cwd(),
        checkout_ref=DEFAULT_CHECKOUT_REF,
        execute_replay=False,
    )
    assert proof["status"] == READY
    assert proof["actual_clean_checkout_performed"] is False
    assert proof["external_ecosystem_integrations_remain_mock"] is True
    assert proof["factory_does_not_self_certify"] is True
    assert proof["certification_ready_not_certified"] is True
    assert proof["official_certification_claimed"] is False
    assert proof["official_certification_granted_by_factory"] is False
    assert validate_actual_clean_checkout_v1_replay_proof(proof) == []


def test_executed_replay_audit_is_present() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["status"] == READY
    assert audit["actual_clean_checkout_performed"] is True
    checkout_ref = audit["checkout_ref"]
    assert isinstance(checkout_ref, str)
    assert checkout_ref
    assert validate_actual_clean_checkout_v1_replay_proof(audit, require_executed=True) == []


def test_replay_proof_lists_required_steps() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    steps_value = audit["replay_steps"]
    assert isinstance(steps_value, list)
    assert set(steps_value) == set(REPLAY_STEPS)


def test_replay_proof_has_command_results() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    command_results = audit["command_results"]
    assert isinstance(command_results, list)
    assert command_results
    command_ids = {result["command_id"] for result in command_results}
    assert "git_clone_local_repository" in command_ids
    assert "validate_phase14n_replay_gate" in command_ids
    assert "run_generated_application_tests" in command_ids
    for result in command_results:
        assert result["returncode"] == 0


def test_replay_proof_preserves_certification_boundary() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    boundary_value = audit["what_sits_between_generated_application_and_certification"]
    assert isinstance(boundary_value, list)
    assert set(boundary_value) == set(CERTIFICATION_BOUNDARY)


def test_replay_proof_preserves_human_gates() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["human_approval_required_for_release_candidate_declaration"] is True
    assert audit["human_approval_required_for_promotion"] is True
    assert audit["human_approval_required_for_merge"] is True
    assert audit["human_approval_required_for_tag"] is True
    assert audit["human_approval_required_for_release"] is True


def test_replay_proof_does_not_mutate_release_or_call_external_systems() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["release_execution_performed"] is False
    assert audit["auto_merge_performed"] is False
    assert audit["auto_tag_performed"] is False
    assert audit["auto_release_performed"] is False
    assert audit["live_provider_calls_performed"] is False
    assert audit["external_system_calls_performed"] is False
    assert audit["arbitrary_shell_execution_performed"] is False


def test_replay_proof_report_is_written(tmp_path: Path) -> None:
    proof = build_actual_clean_checkout_v1_replay_proof(
        source_root=Path.cwd(),
        checkout_ref=DEFAULT_CHECKOUT_REF,
        execute_replay=False,
    )
    output = tmp_path / "actual_clean_checkout_v1_replay_proof.json"
    write_replay_proof(proof, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "actual-clean-checkout-v1-replay-proof.v1"
    assert payload["status"] == READY


def test_phase14o_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14o_actual_clean_checkout_replay.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 14O actual clean-checkout replay proof artifacts validated." in result.stdout


def test_replay_proof_cli_plan_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_actual_clean_checkout_v1_replay_proof.py",
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
