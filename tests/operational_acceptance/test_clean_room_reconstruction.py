from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from factory.documentation import FactStatus, canonical_json
from factory.operational_acceptance import (
    AcceptanceStatus,
    ArtifactAvailability,
    CleanRoomReconstructionError,
    CleanRoomReconstructionEvidence,
    run_clean_room_reconstruction,
    validate_clean_room_reconstruction_evidence,
    write_clean_room_reconstruction_evidence,
)
from factory.operational_acceptance.clean_room import (
    DECLARED_CHILD_ENVIRONMENT,
    NETWORK_DENIAL_BOOTSTRAP,
    SOURCE_DEPENDENCY_PATHS,
    _git_environment,
    _hidden_state_findings,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def proven_clean_room(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[CleanRoomReconstructionEvidence, Path]:
    workspace = tmp_path_factory.mktemp("m2-6c") / "protocol"
    evidence = run_clean_room_reconstruction(ROOT, workspace)
    return evidence, workspace


def test_exact_clean_checkout_exercises_supported_factory_path(
    proven_clean_room: tuple[CleanRoomReconstructionEvidence, Path],
) -> None:
    evidence, workspace = proven_clean_room
    document = evidence.to_dict()

    assert evidence.result.status is AcceptanceStatus.PASS
    assert evidence.result.reconstruction_performed is True
    assert evidence.result.supported_path_executed is True
    assert evidence.result.exit_code == 0
    assert evidence.source_identity.availability is ArtifactAvailability.PRESENT
    assert evidence.source_identity.commit_oid == subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    assert evidence.source_identity.tree_oid == subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    checks = {item.check_id: item for item in evidence.result.checks}
    assert checks["RECONSTRUCTION-PUBLIC-CLONE-HYGIENE"].status is AcceptanceStatus.PASS
    assert checks["HIDDEN-STATE-UNTRACKED-SOURCE-DEPENDENCIES"].observed == []
    assert checks["HIDDEN-STATE-UNDECLARED-ENVIRONMENT"].observed == []
    assert checks["HIDDEN-STATE-PERSONAL-PATHS"].observed == []
    assert checks["RECONSTRUCTION-NO-PREEXISTING-GENERATED-OUTPUT"].status is (
        AcceptanceStatus.PASS
    )
    assert checks["SOURCE-REPOSITORY-NOT-MUTATED"].status is AcceptanceStatus.PASS
    assert document["protocol"]["source_repository_optional_git_locks"] == "DISABLED"
    assert len(document["protocol"]["protocol_implementation_sha256"]) == 64
    output = json.loads(
        (workspace / "execution" / "outputs" / "requirements_ir.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["application"]["app_id"] == "upi_app_factory"
    assert output["application"]["real_payment_calls"] == "disabled"
    assert output["application"]["runtime_llm_calls_default"] == 0
    assert validate_clean_room_reconstruction_evidence(document) is True


def test_canonical_evidence_is_path_neutral_and_non_authoritative(
    proven_clean_room: tuple[CleanRoomReconstructionEvidence, Path], tmp_path: Path
) -> None:
    evidence, workspace = proven_clean_room
    path = tmp_path / "clean-room-evidence.json"
    summary = write_clean_room_reconstruction_evidence(evidence, path)
    encoded = path.read_text(encoding="utf-8")

    assert encoded == canonical_json(evidence.to_dict()) + "\n"
    assert str(ROOT) not in encoded
    assert str(workspace) not in encoded
    assert "/home/" not in encoded
    assert "/tmp/" not in encoded
    assert summary["status"] == "PASS"
    assert evidence.to_dict()["authority_boundary"] == {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
        "self_awarded_readiness": False,
    }
    fact = evidence.machine_evidence_fact()
    assert fact.status is FactStatus.PROVEN
    assert fact.value["result"] == "PASS"
    assert fact.metadata["authority"] == "MACHINE_OBSERVATION_ONLY"


def test_same_source_identity_replays_to_same_canonical_evidence(
    proven_clean_room: tuple[CleanRoomReconstructionEvidence, Path], tmp_path: Path
) -> None:
    first, _workspace = proven_clean_room
    replay = run_clean_room_reconstruction(ROOT, tmp_path / "replay")

    assert replay.result.status is AcceptanceStatus.PASS
    assert replay.result.result_id == first.result.result_id
    assert replay.evidence_id == first.evidence_id
    assert replay.to_json() == first.to_json()


def test_unavailable_git_is_typed_blocked_and_does_not_create_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "unused"
    evidence = run_clean_room_reconstruction(
        ROOT,
        workspace,
        git_executable=tmp_path / "missing-git",
    )

    assert evidence.result.status is AcceptanceStatus.BLOCKED
    assert evidence.result.supported_path_executed is False
    assert not workspace.exists()
    checks = {item.check_id: item for item in evidence.result.checks}
    assert checks["PREREQUISITE-GIT"].status is AcceptanceStatus.BLOCKED
    assert validate_clean_room_reconstruction_evidence(evidence.to_dict()) is True


def test_nonempty_workspace_is_preserved_and_blocks_before_reconstruction(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "maintainer-owned"
    workspace.mkdir()
    marker = workspace / "preserve.txt"
    marker.write_text("preserve", encoding="utf-8")

    evidence = run_clean_room_reconstruction(ROOT, workspace)

    assert evidence.result.status is AcceptanceStatus.BLOCKED
    assert evidence.result.reconstruction_performed is False
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert list(workspace.iterdir()) == [marker]


def test_untracked_declared_source_dependency_is_reported_before_execution(
    tmp_path: Path,
) -> None:
    source = tmp_path / "candidate-source"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(source)],
        check=True,
    )
    hidden = source / "factory" / "hidden_local_dependency.py"
    hidden.write_text("VALUE = 'untracked'\n", encoding="utf-8")
    logical_path = "factory/hidden_local_dependency.py"

    evidence = run_clean_room_reconstruction(
        source,
        tmp_path / "protocol",
        source_dependency_paths=(*SOURCE_DEPENDENCY_PATHS, logical_path),
    )

    assert evidence.result.status is AcceptanceStatus.BLOCKED
    assert evidence.result.supported_path_executed is False
    check = next(
        item
        for item in evidence.result.checks
        if item.check_id == "HIDDEN-STATE-UNTRACKED-SOURCE-DEPENDENCIES"
    )
    assert check.status is AcceptanceStatus.BLOCKED
    assert check.observed == [logical_path]
    assert validate_clean_room_reconstruction_evidence(evidence.to_dict()) is True


def test_hidden_path_and_undeclared_environment_detectors_are_explicit() -> None:
    findings = _hidden_state_findings(
        {
            "factory/example.py": (
                b"import os\n"
                b"PRIVATE = '/home/example/private'\n"
                b"TOKEN = os.getenv('UNDECLARED_TOKEN')\n"
            )
        },
        DECLARED_CHILD_ENVIRONMENT,
    )

    assert findings["personal_paths"] == ["factory/example.py"]
    assert findings["undeclared_environment"] == [
        "factory/example.py:UNDECLARED_TOKEN"
    ]


def test_exercised_hygiene_validator_is_scanned_with_narrow_fixture_exemptions() -> None:
    logical_path = "scripts/validate_public_clone_readiness.py"
    validator = (ROOT / logical_path).read_bytes()

    findings = _hidden_state_findings(
        {logical_path: validator}, DECLARED_CHILD_ENVIRONMENT
    )
    compromised = _hidden_state_findings(
        {
            logical_path: validator
            + b"\nimport os\n"
            + b"PRIVATE = '/home/operator/private'\n"
            + b"TOKEN = os.getenv('UNDECLARED_TOKEN')\n"
        },
        DECLARED_CHILD_ENVIRONMENT,
    )

    assert findings == {
        "home_resolution": [],
        "personal_paths": [],
        "syntax_errors": [],
        "undeclared_environment": [],
    }
    assert compromised["personal_paths"] == [logical_path]
    assert compromised["undeclared_environment"] == [
        f"{logical_path}:UNDECLARED_TOKEN"
    ]


def test_source_git_reads_disable_optional_repository_writes(tmp_path: Path) -> None:
    environment = _git_environment(tmp_path, Path("/declared-tools/git"))

    assert environment["GIT_OPTIONAL_LOCKS"] == "0"


def test_network_denial_bootstrap_rejects_socket_creation(tmp_path: Path) -> None:
    module = tmp_path / "network_probe.py"
    module.write_text("import socket\nsocket.socket()\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            NETWORK_DENIAL_BOOTSTRAP,
            str(tmp_path),
            "network_probe",
        ],
        cwd=tmp_path,
        env=dict(DECLARED_CHILD_ENVIRONMENT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode != 0
    assert "CLEAN_ROOM_NETWORK_DENIED" in completed.stderr


def test_evidence_validator_detects_status_and_authority_tampering(
    proven_clean_room: tuple[CleanRoomReconstructionEvidence, Path],
) -> None:
    evidence, _workspace = proven_clean_room
    tampered = json.loads(evidence.to_json())
    tampered["authority_boundary"]["self_awarded_readiness"] = True
    with pytest.raises(CleanRoomReconstructionError, match="authority boundary"):
        validate_clean_room_reconstruction_evidence(tampered)

    tampered = json.loads(evidence.to_json())
    tampered["result"]["checks"][0]["status"] = "FAIL"
    with pytest.raises(CleanRoomReconstructionError, match="result_sha256"):
        validate_clean_room_reconstruction_evidence(tampered)


def test_package_cli_exposes_clean_room_protocol() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "factory.operational_acceptance", "clean-room", "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0
    assert "no-network clean-room reconstruction" in completed.stdout
