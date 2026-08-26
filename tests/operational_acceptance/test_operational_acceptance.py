from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from factory.documentation import FactStatus, canonical_json
from factory.governance_evolution import ExecutionFingerprint, GovernanceSnapshot
from factory.operational_acceptance import (
    AcceptanceStatus,
    ArtifactAvailability,
    OperationalAcceptanceError,
    build_representative_scenario,
    run_representative_operational_acceptance,
    validate_operational_acceptance_evidence,
    write_operational_acceptance_evidence,
)


ROOT = Path(__file__).resolve().parents[2]


def test_real_requirements_compiler_scenario_emits_bound_pass_evidence(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "representative-run"
    evidence = run_representative_operational_acceptance(ROOT, workspace)
    document = evidence.to_dict()

    assert evidence.result.status is AcceptanceStatus.PASS
    assert document["result"]["status"] == "PASS"
    assert document["result"]["command_executed"] is True
    assert document["result"]["exit_code"] == 0
    assert document["scenario"]["command"] == {
        "argv": [
            "{current_python}",
            "-m",
            "factory.application_engineering.requirements_compiler",
            "validate",
            "--input",
            "inputs/failed_debit_requirements.md",
            "--project-root",
            ".",
            "--output",
            "outputs/requirements_ir.json",
        ],
        "entrypoint": "factory.application_engineering.requirements_compiler:main",
        "interpreter_resolution": (
            "{current_python} resolves to the exact interpreter running this harness; "
            "the result records its implementation, version, and executable digest."
        ),
        "working_directory": "DISPOSABLE_WORKSPACE",
    }
    output = json.loads(
        (workspace / "outputs/requirements_ir.json").read_text(encoding="utf-8")
    )
    assert output["application"]["app_id"] == "upi_app_factory"
    assert output["application"]["real_payment_calls"] == "disabled"
    assert output["application"]["runtime_llm_calls_default"] == 0
    assert output["traceability"]
    assert validate_operational_acceptance_evidence(document) is True


def test_same_inputs_produce_same_scenario_result_and_evidence_identity(
    tmp_path: Path,
) -> None:
    first = run_representative_operational_acceptance(ROOT, tmp_path / "one")
    second = run_representative_operational_acceptance(ROOT, tmp_path / "two")

    assert first.scenario.scenario_id == second.scenario.scenario_id
    assert first.result.result_id == second.result.result_id
    assert first.evidence_id == second.evidence_id
    assert first.to_json() == second.to_json()


def test_scenario_reuses_governance_snapshot_and_execution_fingerprint() -> None:
    scenario = build_representative_scenario(ROOT)

    assert isinstance(scenario.governance_snapshot, GovernanceSnapshot)
    assert isinstance(scenario.execution_fingerprint, ExecutionFingerprint)
    assert (
        scenario.execution_fingerprint.governance_snapshot_identity
        == scenario.governance_snapshot.snapshot_id
    )
    assert scenario.execution_fingerprint.requirement_identity.startswith(
        "REQUIREMENT-INPUT-"
    )
    assert scenario.execution_fingerprint.evidence_snapshot_identity == (
        "EVIDENCE-SNAPSHOT-NOT-APPLICABLE-NO-UPSTREAM-EVIDENCE-INPUT"
    )


def test_machine_evidence_projection_authenticates_record_without_granting_authority(
    tmp_path: Path,
) -> None:
    evidence = run_representative_operational_acceptance(ROOT, tmp_path / "fact-run")
    fact = evidence.machine_evidence_fact()
    graph = evidence.evidence_graph()

    assert fact.status is FactStatus.PROVEN
    assert fact.node_type == "AUTHENTICATED_MACHINE_EVIDENCE"
    assert fact.value["result"] == "PASS"
    assert fact.metadata["authority"] == "MACHINE_OBSERVATION_ONLY"
    assert graph.node(fact.node_id) == fact
    assert evidence.to_dict()["authority_boundary"] == {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
        "self_awarded_readiness": False,
    }


def test_missing_prerequisites_return_blocked_without_executing(tmp_path: Path) -> None:
    evidence = run_representative_operational_acceptance(
        tmp_path / "absent-source-checkout", tmp_path / "unused-workspace"
    )

    assert evidence.result.status is AcceptanceStatus.BLOCKED
    assert evidence.result.command_executed is False
    assert evidence.result.exit_code is None
    assert any(
        item.status is AcceptanceStatus.BLOCKED for item in evidence.result.checks
    )
    assert not (tmp_path / "unused-workspace").exists()
    assert validate_operational_acceptance_evidence(evidence.to_dict()) is True


def test_source_checkout_or_nonempty_workspace_is_rejected(tmp_path: Path) -> None:
    source_result = run_representative_operational_acceptance(ROOT, ROOT)
    assert source_result.result.status is AcceptanceStatus.BLOCKED
    assert source_result.result.command_executed is False

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    marker = nonempty / "belongs-to-maintainer.txt"
    marker.write_text("preserve", encoding="utf-8")
    nonempty_result = run_representative_operational_acceptance(ROOT, nonempty)
    assert nonempty_result.result.status is AcceptanceStatus.BLOCKED
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_serialized_evidence_validation_detects_tampering(tmp_path: Path) -> None:
    evidence = run_representative_operational_acceptance(ROOT, tmp_path / "tamper-run")
    tampered = json.loads(evidence.to_json())
    tampered["authority_boundary"]["self_awarded_readiness"] = True

    with pytest.raises(OperationalAcceptanceError, match="authority boundary"):
        validate_operational_acceptance_evidence(tampered)

    tampered = json.loads(evidence.to_json())
    tampered["result"]["checks"][0]["status"] = "FAIL"
    with pytest.raises(OperationalAcceptanceError, match="result_sha256"):
        validate_operational_acceptance_evidence(tampered)


def test_written_evidence_is_canonical_and_contains_no_workspace_path(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "write-run"
    evidence = run_representative_operational_acceptance(ROOT, workspace)
    evidence_path = workspace / "evidence" / "operational_acceptance.json"
    summary = write_operational_acceptance_evidence(evidence, evidence_path)

    encoded = evidence_path.read_text(encoding="utf-8")
    assert encoded == canonical_json(evidence.to_dict()) + "\n"
    assert str(tmp_path) not in encoded
    assert summary["evidence_id"] == evidence.evidence_id
    assert summary["status"] == "PASS"


def test_package_cli_returns_machine_summary_and_writes_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "cli-run"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.operational_acceptance",
            "--project-root",
            str(ROOT),
            "--workspace",
            str(workspace),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    summary = json.loads(completed.stdout)
    assert summary["status"] == "PASS"
    assert summary["evidence_artifact"] == "operational_acceptance_evidence.json"
    document = json.loads(
        (workspace / "operational_acceptance_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_operational_acceptance_evidence(document) is True


def test_output_artifact_identity_is_explicit_and_portable(tmp_path: Path) -> None:
    evidence = run_representative_operational_acceptance(ROOT, tmp_path / "artifact-run")
    artifact = evidence.result.output_artifacts[0]

    assert artifact.logical_path == "outputs/requirements_ir.json"
    assert artifact.availability is ArtifactAvailability.PRESENT
    assert artifact.sha256 is not None and len(artifact.sha256) == 64
    assert artifact.size_bytes is not None and artifact.size_bytes > 0
