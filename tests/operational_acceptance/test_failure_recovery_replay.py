from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from factory.documentation import FactStatus, canonical_json
from factory.operational_acceptance import (
    FailureClass,
    FailureRecoveryReplayError,
    FaultClass,
    ProofVerdict,
    RecoveryAction,
    ReplayIdentityBinding,
    build_recovery_decision,
    run_failure_recovery_replay,
    validate_failure_recovery_replay_evidence,
    write_failure_recovery_replay_evidence,
)


ROOT = Path(__file__).resolve().parents[2]


def test_executable_fault_is_detected_and_failed_evidence_is_preserved(
    tmp_path: Path,
) -> None:
    failed_workspace = tmp_path / "failed-run"
    replay_workspace = tmp_path / "replay-run"

    evidence = run_failure_recovery_replay(
        ROOT, failed_workspace, replay_workspace
    )

    assert evidence.fault_injection.fault_class is (
        FaultClass.EXECUTION_OUTPUT_UNAVAILABLE
    )
    assert evidence.failure_record.failure_class is (
        FailureClass.EVIDENCE_INTEGRITY_FAILURE
    )
    assert evidence.failure_record.first_authoritative_failure.check_id == (
        "OUTPUT-ARTIFACT-IDENTITY"
    )
    assert evidence.failure_record.first_authoritative_failure.verdict is (
        ProofVerdict.DISPROVEN
    )
    assert not (failed_workspace / "outputs/requirements_ir.json").exists()
    quarantined = (
        failed_workspace
        / "faults/quarantine/outputs/requirements_ir.json"
    )
    assert quarantined.is_file()
    assert evidence.fault_injection.quarantine_artifact.sha256 == (
        evidence.fault_injection.target_before.sha256
    )
    document = evidence.to_dict()
    assert document["failure_record"]["failed_evidence_preserved"] is True
    assert document["source_acceptance_evidence"]["evidence_id"] == (
        evidence.failure_record.source_evidence_id
    )
    assert validate_failure_recovery_replay_evidence(document) is True


def test_recovery_replays_exact_identites_without_moving_governance_or_requirements(
    tmp_path: Path,
) -> None:
    evidence = run_failure_recovery_replay(
        ROOT, tmp_path / "failed", tmp_path / "replay"
    )
    source = evidence.source_acceptance_evidence
    replay = evidence.replay_acceptance_evidence

    assert evidence.recovery_decision.action is RecoveryAction.REPLAY_EXACT_BOUND_INPUTS
    assert evidence.recovery_decision.verdict is ProofVerdict.PROVEN
    assert replay is not None
    assert evidence.replay_record.verdict is ProofVerdict.PROVEN
    assert source.scenario.scenario_id == replay.scenario.scenario_id
    assert (
        source.scenario.execution_fingerprint.fingerprint_id
        == replay.scenario.execution_fingerprint.fingerprint_id
    )
    assert (
        source.scenario.execution_fingerprint.governance_snapshot_identity
        == replay.scenario.execution_fingerprint.governance_snapshot_identity
    )
    assert (
        source.scenario.execution_fingerprint.requirement_identity
        == replay.scenario.execution_fingerprint.requirement_identity
    )
    assert source.result.result_id == replay.result.result_id
    assert source.evidence_id == replay.evidence_id
    checks = {item.check_id: item for item in evidence.replay_record.checks}
    assert checks["GOVERNANCE-PIN-IDENTITY"].verdict is ProofVerdict.PROVEN
    assert checks["REQUIREMENT-IDENTITY"].verdict is ProofVerdict.PROVEN
    assert checks["VALIDATION-GATES"].verdict is ProofVerdict.PROVEN


def test_same_fault_and_bound_inputs_produce_same_canonical_evidence(
    tmp_path: Path,
) -> None:
    first = run_failure_recovery_replay(
        ROOT, tmp_path / "failed-one", tmp_path / "replay-one"
    )
    second = run_failure_recovery_replay(
        ROOT, tmp_path / "failed-two", tmp_path / "replay-two"
    )

    assert first.fault_injection.injection_id == second.fault_injection.injection_id
    assert first.failure_record.failure_id == second.failure_record.failure_id
    assert first.recovery_decision.decision_id == second.recovery_decision.decision_id
    assert first.replay_record.replay_id == second.replay_record.replay_id
    assert first.evidence_id == second.evidence_id
    assert first.to_json() == second.to_json()


def test_missing_replay_identity_is_unknown_and_unmeasured_is_not_invented() -> None:
    binding = ReplayIdentityBinding.from_identities(
        evidence_snapshot_identity="EVIDENCE-SNAPSHOT-EXACT",
        factory_source_identity="FACTORY-SOURCE-EXACT",
        governance_snapshot_identity="GOVERNANCE-MISSING-deadbeef",
        requirement_identity="REQUIREMENT-EXACT",
        tool_config_identity=None,
        unmeasured_fields=("tool_config_identity",),
    )
    assessments = {item.field_name: item for item in binding.assessments}

    assert assessments["governance_snapshot_identity"].verdict is ProofVerdict.UNKNOWN
    assert assessments["tool_config_identity"].verdict is ProofVerdict.NOT_MEASURED
    assert assessments["tool_config_identity"].identity is None
    decision = build_recovery_decision("OPERATIONAL-FAILURE-EXAMPLE", binding)
    assert decision.action is RecoveryAction.STOP_MISSING_IDENTITY
    assert decision.verdict is ProofVerdict.UNKNOWN


def test_fact_projection_authenticates_observation_without_recovery_authority(
    tmp_path: Path,
) -> None:
    evidence = run_failure_recovery_replay(
        ROOT, tmp_path / "failed-fact", tmp_path / "replay-fact"
    )
    fact = evidence.machine_evidence_fact()

    assert fact.status is FactStatus.PROVEN
    assert fact.value["replay_verdict"] == "PROVEN"
    assert fact.value["first_authoritative_failure"] == (
        "OUTPUT-ARTIFACT-IDENTITY"
    )
    assert fact.metadata["authority"] == "MACHINE_OBSERVATION_ONLY"
    assert evidence.evidence_graph().node(fact.node_id) == fact
    assert evidence.to_dict()["authority_boundary"] == {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
        "self_awarded_recovery_authority": False,
    }


def test_serialized_failure_replay_evidence_detects_tampering(tmp_path: Path) -> None:
    evidence = run_failure_recovery_replay(
        ROOT, tmp_path / "failed-tamper", tmp_path / "replay-tamper"
    )
    tampered = json.loads(evidence.to_json())
    tampered["fault_injection"]["authority_effects"]["gate_weakening"] = True

    with pytest.raises(
        FailureRecoveryReplayError,
        match="injection_sha256|governed authority",
    ):
        validate_failure_recovery_replay_evidence(tampered)

    tampered = json.loads(evidence.to_json())
    tampered["recovery_decision"]["replay_binding"]["assessments"][0][
        "identity"
    ] = "INVENTED-IDENTITY"
    with pytest.raises(
        FailureRecoveryReplayError,
        match="decision_sha256|binding changed",
    ):
        validate_failure_recovery_replay_evidence(tampered)


def test_written_evidence_is_canonical_portable_and_cli_executable(
    tmp_path: Path,
) -> None:
    failed_workspace = tmp_path / "failed-write"
    replay_workspace = tmp_path / "replay-write"
    evidence = run_failure_recovery_replay(
        ROOT, failed_workspace, replay_workspace
    )
    path = replay_workspace / "evidence/failure_recovery_replay.json"
    summary = write_failure_recovery_replay_evidence(evidence, path)
    encoded = path.read_text(encoding="utf-8")

    assert encoded == canonical_json(evidence.to_dict()) + "\n"
    assert str(tmp_path) not in encoded
    assert summary["status"] == "PROVEN"
    assert summary["first_authoritative_failure"] == "OUTPUT-ARTIFACT-IDENTITY"

    cli_failed = tmp_path / "cli-failed"
    cli_replay = tmp_path / "cli-replay"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.operational_acceptance",
            "failure-recovery",
            "--project-root",
            str(ROOT),
            "--failure-workspace",
            str(cli_failed),
            "--replay-workspace",
            str(cli_replay),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    cli_summary = json.loads(completed.stdout)
    assert cli_summary["status"] == "PROVEN"
    assert cli_summary["first_authoritative_failure"] == (
        "OUTPUT-ARTIFACT-IDENTITY"
    )
    cli_document = json.loads(
        (cli_replay / "failure_recovery_replay_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_failure_recovery_replay_evidence(cli_document) is True
