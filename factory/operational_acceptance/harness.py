"""Deterministic executable operational-acceptance evidence.

The harness executes the supported requirements-compiler entrypoint in a
caller-owned disposable workspace.  Its record is a machine observation, not
readiness authority: exact input and output identities are bound to the M2.4
fact/provenance primitives and the M2.5 execution fingerprint contract.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
from typing import Any, ClassVar, Iterable, Mapping, cast

from factory.documentation import (
    EvidenceGraph,
    FactNode,
    FactStatus,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from factory.documentation.facts import FactModelError, _identifier
from factory.governance_evolution import (
    ExecutionFingerprint,
    GovernanceSnapshot,
    GovernanceSourceBinding,
)


class OperationalAcceptanceError(FactModelError):
    """Raised when an acceptance contract or evidence record is ambiguous."""


class AcceptanceStatus(str, Enum):
    """Closed operational outcome vocabulary."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ArtifactRole(str, Enum):
    FACTORY_SOURCE = "FACTORY_SOURCE"
    REQUIREMENT_INPUT = "REQUIREMENT_INPUT"
    GOVERNANCE_INPUT = "GOVERNANCE_INPUT"
    EXECUTION_OUTPUT = "EXECUTION_OUTPUT"


class ArtifactAvailability(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"


SCENARIO_KEY = "OA-FAILED-DEBIT-REQUIREMENTS-COMPILER-V1"
REQUIREMENT_PATH = "tests/fixtures/phase53/failed_debit_requirements.md"
GOVERNANCE_PATH = "config/quality_assurance/defaults.json"
FACTORY_SOURCE_PATHS = (
    "factory/application_engineering/requirements_compiler.py",
    "factory/documentation/facts.py",
    "factory/governance_evolution/snapshots.py",
    "factory/operational_acceptance/failure_recovery.py",
    "factory/operational_acceptance/harness.py",
)
OUTPUT_PATH = "outputs/requirements_ir.json"
COPIED_INPUT_PATH = "inputs/failed_debit_requirements.md"
EVIDENCE_INPUT_IDENTITY = (
    "EVIDENCE-SNAPSHOT-NOT-APPLICABLE-NO-UPSTREAM-EVIDENCE-INPUT"
)
_SHA256_PATTERN = "0123456789abcdef"


def _stable_identifier(value: str, field_name: str) -> str:
    try:
        return _identifier(value, field_name)
    except FactModelError as exc:
        raise OperationalAcceptanceError(str(exc)) from exc


def _stable_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise OperationalAcceptanceError(f"{field_name} must be non-empty normalized text")
    return value


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _SHA256_PATTERN for character in value)
    )


def _logical_path(value: str, field_name: str) -> str:
    _stable_text(value, field_name)
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
        raise OperationalAcceptanceError(
            f"{field_name} must be a normalized workspace-relative POSIX path"
        )
    normalized = path.as_posix()
    if normalized != value or "\\" in value:
        raise OperationalAcceptanceError(
            f"{field_name} must be a normalized workspace-relative POSIX path"
        )
    return normalized


def _normalized_collection(
    values: Iterable[Any], field_name: str, expected_type: type[Any]
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise OperationalAcceptanceError(f"{field_name} must be a collection")
    try:
        normalized = tuple(values)
    except TypeError as exc:
        raise OperationalAcceptanceError(f"{field_name} must be a collection") from exc
    if any(not isinstance(item, expected_type) for item in normalized):
        raise OperationalAcceptanceError(
            f"{field_name} must contain {expected_type.__name__} values"
        )
    return normalized


def _detached_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OperationalAcceptanceError(f"{field_name} must be a canonical JSON object")
    try:
        detached = json.loads(canonical_json(dict(value)))
    except FactModelError as exc:
        raise OperationalAcceptanceError(str(exc)) from exc
    return cast(Mapping[str, Any], detached)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArtifactIdentity:
    """Portable exact-byte identity, including explicit missing state."""

    logical_path: str
    role: ArtifactRole
    availability: ArtifactAvailability
    sha256: str | None
    size_bytes: int | None

    def __post_init__(self) -> None:
        _logical_path(self.logical_path, "logical_path")
        if not isinstance(self.role, ArtifactRole):
            raise OperationalAcceptanceError("role must use ArtifactRole")
        if not isinstance(self.availability, ArtifactAvailability):
            raise OperationalAcceptanceError(
                "availability must use ArtifactAvailability"
            )
        if self.availability is ArtifactAvailability.PRESENT:
            if not _is_sha256(self.sha256):
                raise OperationalAcceptanceError("present artifacts require a SHA-256 identity")
            if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
                raise OperationalAcceptanceError(
                    "present artifacts require a non-negative byte size"
                )
        elif self.sha256 is not None or self.size_bytes is not None:
            raise OperationalAcceptanceError(
                "missing artifacts cannot carry an asserted content identity"
            )

    @classmethod
    def observe(
        cls, root: Path, logical_path: str, role: ArtifactRole
    ) -> ArtifactIdentity:
        normalized = _logical_path(logical_path, "logical_path")
        path = root / PurePosixPath(normalized)
        if not path.is_file():
            return cls(normalized, role, ArtifactAvailability.MISSING, None, None)
        return cls(
            normalized,
            role,
            ArtifactAvailability.PRESENT,
            _sha256_file(path),
            path.stat().st_size,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability.value,
            "logical_path": self.logical_path,
            "role": self.role.value,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class CommandContract:
    """Exact portable argv and import entrypoint contract."""

    entrypoint: str
    argv: tuple[str, ...]
    working_directory: str
    interpreter_resolution: str

    def __post_init__(self) -> None:
        _stable_identifier(self.entrypoint, "entrypoint")
        _stable_identifier(self.working_directory, "working_directory")
        _stable_text(self.interpreter_resolution, "interpreter_resolution")
        if isinstance(self.argv, (str, bytes)) or not self.argv:
            raise OperationalAcceptanceError("argv must be a non-empty collection")
        if any(
            not isinstance(item, str) or not item or item != item.strip()
            for item in self.argv
        ):
            raise OperationalAcceptanceError("argv must contain normalized string tokens")
        object.__setattr__(self, "argv", tuple(self.argv))

    def to_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "entrypoint": self.entrypoint,
            "interpreter_resolution": self.interpreter_resolution,
            "working_directory": self.working_directory,
        }


@dataclass(frozen=True)
class EnvironmentContract:
    """Stable prerequisites and safety controls, not observed runtime claims."""

    contract_id: str = "LOCAL-DETERMINISTIC-MOCK-SAFE-COMPILER-V1"
    python_requirement: str = "CPYTHON_3_10_OR_NEWER"
    workspace_requirement: str = "NEW_EMPTY_DISPOSABLE_WORKSPACE"
    source_checkout_requirement: str = "DECLARED_READ_ONLY_SOURCE_CHECKOUT"
    network_dependency: str = "NOT_REQUIRED"
    external_system_dependency: str = "NOT_REQUIRED"
    llm_execution: str = "DISABLED"
    real_payment_calls: str = "DISABLED"

    def __post_init__(self) -> None:
        for field_name, value in self.to_dict().items():
            _stable_identifier(str(value), field_name)

    def to_dict(self) -> dict[str, str]:
        return {
            "contract_id": self.contract_id,
            "external_system_dependency": self.external_system_dependency,
            "llm_execution": self.llm_execution,
            "network_dependency": self.network_dependency,
            "python_requirement": self.python_requirement,
            "real_payment_calls": self.real_payment_calls,
            "source_checkout_requirement": self.source_checkout_requirement,
            "workspace_requirement": self.workspace_requirement,
        }


@dataclass(frozen=True)
class AcceptanceCheck:
    """One deterministic comparison used to derive the scenario result."""

    check_id: str
    status: AcceptanceStatus
    expected: Any
    observed: Any
    explanation: str

    def __post_init__(self) -> None:
        _stable_identifier(self.check_id, "check_id")
        if not isinstance(self.status, AcceptanceStatus):
            raise OperationalAcceptanceError("check status must use AcceptanceStatus")
        _stable_text(self.explanation, "check explanation")
        object.__setattr__(
            self,
            "expected",
            json.loads(canonical_json(self.expected)),
        )
        object.__setattr__(
            self,
            "observed",
            json.loads(canonical_json(self.observed)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "expected": self.expected,
            "explanation": self.explanation,
            "observed": self.observed,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class OperationalAcceptanceScenario:
    """Immutable acceptance scenario bound to exact governed inputs."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.operational-acceptance-scenario.v1"

    scenario_key: str
    title: str
    objective: str
    command: CommandContract
    environment_contract: EnvironmentContract
    factory_sources: tuple[ArtifactIdentity, ...]
    requirement_inputs: tuple[ArtifactIdentity, ...]
    governance_inputs: tuple[ArtifactIdentity, ...]
    governance_snapshot: GovernanceSnapshot | None
    execution_fingerprint: ExecutionFingerprint
    expected_output_paths: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _stable_identifier(self.scenario_key, "scenario_key")
        _stable_text(self.title, "title")
        _stable_text(self.objective, "objective")
        if not isinstance(self.command, CommandContract):
            raise OperationalAcceptanceError("command must use CommandContract")
        if not isinstance(self.environment_contract, EnvironmentContract):
            raise OperationalAcceptanceError(
                "environment_contract must use EnvironmentContract"
            )
        if not isinstance(self.execution_fingerprint, ExecutionFingerprint):
            raise OperationalAcceptanceError(
                "execution_fingerprint must use the M2.5 ExecutionFingerprint"
            )
        collections = (
            ("factory_sources", self.factory_sources, ArtifactRole.FACTORY_SOURCE),
            ("requirement_inputs", self.requirement_inputs, ArtifactRole.REQUIREMENT_INPUT),
            ("governance_inputs", self.governance_inputs, ArtifactRole.GOVERNANCE_INPUT),
        )
        for field_name, values, role in collections:
            normalized = _normalized_collection(values, field_name, ArtifactIdentity)
            if not normalized or any(item.role is not role for item in normalized):
                raise OperationalAcceptanceError(
                    f"{field_name} must contain at least one {role.value} identity"
                )
            paths = [item.logical_path for item in normalized]
            if len(paths) != len(set(paths)):
                raise OperationalAcceptanceError(f"{field_name} paths must be unique")
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(normalized, key=lambda item: item.logical_path)),
            )
        outputs = tuple(
            sorted(
                _logical_path(item, "expected_output_paths")
                for item in self.expected_output_paths
            )
        )
        if not outputs or len(outputs) != len(set(outputs)):
            raise OperationalAcceptanceError(
                "expected_output_paths must contain unique paths"
            )
        limitations = tuple(
            sorted(_stable_text(item, "limitation") for item in self.limitations)
        )
        if not limitations or len(limitations) != len(set(limitations)):
            raise OperationalAcceptanceError("scenario limitations must be unique and explicit")
        if self.governance_snapshot is not None and not isinstance(
            self.governance_snapshot, GovernanceSnapshot
        ):
            raise OperationalAcceptanceError(
                "governance_snapshot must use the M2.5 GovernanceSnapshot"
            )
        expected_governance_identity = (
            self.governance_snapshot.snapshot_id
            if self.governance_snapshot is not None
            else _missing_identity("GOVERNANCE", GOVERNANCE_PATH)
        )
        if (
            self.execution_fingerprint.governance_snapshot_identity
            != expected_governance_identity
        ):
            raise OperationalAcceptanceError(
                "execution fingerprint does not bind the scenario governance identity"
            )
        object.__setattr__(self, "expected_output_paths", outputs)
        object.__setattr__(self, "limitations", limitations)

    def identity_payload(self) -> dict[str, Any]:
        governance: dict[str, Any]
        if self.governance_snapshot is None:
            governance = {
                "availability": ArtifactAvailability.MISSING.value,
                "snapshot": None,
            }
        else:
            governance = {
                "availability": ArtifactAvailability.PRESENT.value,
                "snapshot": self.governance_snapshot.to_dict(),
            }
        return {
            "command": self.command.to_dict(),
            "environment_contract": self.environment_contract.to_dict(),
            "evidence_input": {
                "applicability": AcceptanceStatus.NOT_APPLICABLE.value,
                "identity": EVIDENCE_INPUT_IDENTITY,
                "reason": (
                    "This scenario consumes source, requirements, and governance; "
                    "no upstream evidence result is used as an execution input."
                ),
            },
            "execution_fingerprint": self.execution_fingerprint.to_dict(),
            "expected_output_paths": list(self.expected_output_paths),
            "factory_sources": [item.to_dict() for item in self.factory_sources],
            "governance_inputs": [item.to_dict() for item in self.governance_inputs],
            "governance_snapshot": governance,
            "limitations": list(self.limitations),
            "objective": self.objective,
            "requirement_inputs": [item.to_dict() for item in self.requirement_inputs],
            "scenario_key": self.scenario_key,
            "schema_version": self.SCHEMA_VERSION,
            "title": self.title,
        }

    @property
    def scenario_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def scenario_id(self) -> str:
        return f"OPERATIONAL-ACCEPTANCE-SCENARIO-{self.scenario_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.scenario_sha256,
        }


@dataclass(frozen=True)
class OperationalAcceptanceResult:
    """Evidence-derived result; no caller-supplied readiness boolean exists."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.operational-acceptance-result.v1"

    status: AcceptanceStatus
    command_executed: bool
    exit_code: int | None
    checks: tuple[AcceptanceCheck, ...]
    output_artifacts: tuple[ArtifactIdentity, ...]
    stdout_sha256: str | None
    stderr_sha256: str | None
    environment_observation: Mapping[str, Any]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, AcceptanceStatus):
            raise OperationalAcceptanceError("result status must use AcceptanceStatus")
        if not isinstance(self.command_executed, bool):
            raise OperationalAcceptanceError("command_executed must be an explicit boolean")
        if self.exit_code is not None and not isinstance(self.exit_code, int):
            raise OperationalAcceptanceError("exit_code must be an integer or null")
        checks = _normalized_collection(self.checks, "checks", AcceptanceCheck)
        if not checks:
            raise OperationalAcceptanceError("results require deterministic checks")
        check_ids = [item.check_id for item in checks]
        if len(check_ids) != len(set(check_ids)):
            raise OperationalAcceptanceError("check IDs must be unique")
        artifacts = _normalized_collection(
            self.output_artifacts, "output_artifacts", ArtifactIdentity
        )
        if any(item.role is not ArtifactRole.EXECUTION_OUTPUT for item in artifacts):
            raise OperationalAcceptanceError(
                "output_artifacts must use the EXECUTION_OUTPUT role"
            )
        paths = [item.logical_path for item in artifacts]
        if len(paths) != len(set(paths)):
            raise OperationalAcceptanceError("output artifact paths must be unique")
        if self.command_executed:
            if not _is_sha256(self.stdout_sha256) or not _is_sha256(self.stderr_sha256):
                raise OperationalAcceptanceError(
                    "executed commands require stdout and stderr SHA-256 identities"
                )
        elif any(
            value is not None
            for value in (self.exit_code, self.stdout_sha256, self.stderr_sha256)
        ):
            raise OperationalAcceptanceError(
                "unexecuted commands cannot carry process observations"
            )
        if self.status is AcceptanceStatus.PASS:
            if not self.command_executed or self.exit_code != 0:
                raise OperationalAcceptanceError("PASS requires a successful command execution")
            if any(item.status is not AcceptanceStatus.PASS for item in checks):
                raise OperationalAcceptanceError("PASS requires every check to pass")
        elif self.status is AcceptanceStatus.FAIL:
            if not self.command_executed:
                raise OperationalAcceptanceError("FAIL requires an attempted command")
            if not any(item.status is AcceptanceStatus.FAIL for item in checks):
                raise OperationalAcceptanceError("FAIL requires at least one failed check")
        elif self.status is AcceptanceStatus.BLOCKED:
            if self.command_executed:
                raise OperationalAcceptanceError("BLOCKED must stop before command execution")
            if not any(item.status is AcceptanceStatus.BLOCKED for item in checks):
                raise OperationalAcceptanceError("BLOCKED requires a blocked prerequisite")
        elif self.command_executed:
            raise OperationalAcceptanceError("NOT_APPLICABLE must not execute a command")
        observation = _detached_mapping(
            self.environment_observation, "environment_observation"
        )
        limitations = tuple(
            sorted(_stable_text(item, "result limitation") for item in self.limitations)
        )
        if not limitations or len(limitations) != len(set(limitations)):
            raise OperationalAcceptanceError("result limitations must be unique and explicit")
        object.__setattr__(self, "checks", tuple(sorted(checks, key=lambda item: item.check_id)))
        object.__setattr__(
            self,
            "output_artifacts",
            tuple(sorted(artifacts, key=lambda item: item.logical_path)),
        )
        object.__setattr__(self, "environment_observation", observation)
        object.__setattr__(self, "limitations", limitations)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "checks": [item.to_dict() for item in self.checks],
            "command_executed": self.command_executed,
            "environment_observation": dict(self.environment_observation),
            "exit_code": self.exit_code,
            "limitations": list(self.limitations),
            "output_artifacts": [item.to_dict() for item in self.output_artifacts],
            "schema_version": self.SCHEMA_VERSION,
            "status": self.status.value,
            "stderr_sha256": self.stderr_sha256,
            "stdout_sha256": self.stdout_sha256,
        }

    @property
    def result_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def result_id(self) -> str:
        return f"OPERATIONAL-ACCEPTANCE-RESULT-{self.result_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "result_id": self.result_id,
            "result_sha256": self.result_sha256,
        }


@dataclass(frozen=True)
class OperationalAcceptanceEvidence:
    """Canonical evidence envelope with explicit non-authority semantics."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.operational-acceptance-evidence.v1"

    scenario: OperationalAcceptanceScenario
    result: OperationalAcceptanceResult
    limitations: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, OperationalAcceptanceScenario):
            raise OperationalAcceptanceError(
                "scenario must use OperationalAcceptanceScenario"
            )
        if not isinstance(self.result, OperationalAcceptanceResult):
            raise OperationalAcceptanceError("result must use OperationalAcceptanceResult")
        object.__setattr__(
            self,
            "limitations",
            tuple(sorted(set((*self.scenario.limitations, *self.result.limitations)))),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_boundary": {
                "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
                "ai_authority": "NONE",
                "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
                "self_awarded_readiness": False,
            },
            "identity_scope": "CANONICAL_EVIDENCE_CORE",
            "limitations": list(self.limitations),
            "result": self.result.to_dict(),
            "scenario": self.scenario.to_dict(),
            "schema_version": self.SCHEMA_VERSION,
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def evidence_id(self) -> str:
        return f"OPERATIONAL-ACCEPTANCE-EVIDENCE-{self.evidence_sha256}"

    @property
    def provenance_binding(self) -> ProvenanceBinding:
        return ProvenanceBinding(
            source_id=f"SOURCE-OPERATIONAL-ACCEPTANCE-{self.evidence_sha256}",
            revision=self.scenario.execution_fingerprint.fingerprint_id,
            content_sha256=self.evidence_sha256,
            source_type="MACHINE_EXECUTION_RECORD",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "evidence_id": self.evidence_id,
            "evidence_sha256": self.evidence_sha256,
            "provenance": self.provenance_binding.to_dict(),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def machine_evidence_fact(self) -> FactNode:
        """Project the record into M2.4 facts without granting acceptance authority."""
        return FactNode(
            node_id=f"FACT-OPERATIONAL-ACCEPTANCE-{self.evidence_sha256}",
            node_type="AUTHENTICATED_MACHINE_EVIDENCE",
            status=FactStatus.PROVEN,
            value={
                "evidence_id": self.evidence_id,
                "result": self.result.status.value,
                "scenario_id": self.scenario.scenario_id,
            },
            provenance=(self.provenance_binding,),
            metadata={
                "authority": "MACHINE_OBSERVATION_ONLY",
                "limitations": list(self.limitations),
            },
        )

    def evidence_graph(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=(self.machine_evidence_fact(),))


def _missing_identity(prefix: str, logical_path: str) -> str:
    return f"{prefix}-MISSING-{canonical_sha256({'logical_path': logical_path})}"


def _aggregate_identity(prefix: str, artifacts: Iterable[ArtifactIdentity]) -> str:
    payload = [item.to_dict() for item in sorted(artifacts, key=lambda item: item.logical_path)]
    return f"{prefix}-{canonical_sha256(payload)}"


def _governance_snapshot(
    project_root: Path, artifact: ArtifactIdentity
) -> GovernanceSnapshot | None:
    if artifact.availability is ArtifactAvailability.MISSING or artifact.sha256 is None:
        return None
    try:
        loaded = json.loads((project_root / GOVERNANCE_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    binding = GovernanceSourceBinding(
        authority_id="REPOSITORY-GOVERNANCE",
        source_id="CONFIG-QUALITY-ASSURANCE-DEFAULTS",
        revision=f"sha256:{artifact.sha256}",
        content_sha256=artifact.sha256,
        source_type="REPOSITORY_GOVERNANCE_CONFIG",
    )
    return GovernanceSnapshot(
        version_id="m2.6b-operational-acceptance-binding.v1",
        payload=loaded,
        source_bindings=(binding,),
    )


def build_representative_scenario(project_root: Path) -> OperationalAcceptanceScenario:
    """Bind the representative supported compiler flow without executing it."""
    root = project_root.resolve()
    factory_sources = tuple(
        ArtifactIdentity.observe(root, path, ArtifactRole.FACTORY_SOURCE)
        for path in FACTORY_SOURCE_PATHS
    )
    requirement = ArtifactIdentity.observe(
        root, REQUIREMENT_PATH, ArtifactRole.REQUIREMENT_INPUT
    )
    governance = ArtifactIdentity.observe(
        root, GOVERNANCE_PATH, ArtifactRole.GOVERNANCE_INPUT
    )
    snapshot = _governance_snapshot(root, governance)
    environment = EnvironmentContract()
    command = CommandContract(
        entrypoint="factory.application_engineering.requirements_compiler:main",
        argv=(
            "{current_python}",
            "-m",
            "factory.application_engineering.requirements_compiler",
            "validate",
            "--input",
            COPIED_INPUT_PATH,
            "--project-root",
            ".",
            "--output",
            OUTPUT_PATH,
        ),
        working_directory="DISPOSABLE_WORKSPACE",
        interpreter_resolution=(
            "{current_python} resolves to the exact interpreter running this harness; "
            "the result records its implementation, version, and executable digest."
        ),
    )
    factory_source_identity = _aggregate_identity(
        "FACTORY-SOURCE-SNAPSHOT", factory_sources
    )
    requirement_identity = (
        f"REQUIREMENT-INPUT-{requirement.sha256}"
        if requirement.sha256 is not None
        else _missing_identity("REQUIREMENT", REQUIREMENT_PATH)
    )
    governance_identity = (
        snapshot.snapshot_id
        if snapshot is not None
        else _missing_identity("GOVERNANCE", GOVERNANCE_PATH)
    )
    tool_config_identity = (
        "TOOL-CONFIG-"
        + canonical_sha256(
            {
                "command": command.to_dict(),
                "environment_contract": environment.to_dict(),
            }
        )
    )
    fingerprint = ExecutionFingerprint(
        factory_source_identity=factory_source_identity,
        requirement_identity=requirement_identity,
        governance_snapshot_identity=governance_identity,
        evidence_snapshot_identity=EVIDENCE_INPUT_IDENTITY,
        tool_config_identity=tool_config_identity,
    )
    return OperationalAcceptanceScenario(
        scenario_key=SCENARIO_KEY,
        title="Compile and validate representative failed-debit requirements",
        objective=(
            "Prove a maintainer can execute a real local factory requirements workflow "
            "and inspect deterministic machine evidence."
        ),
        command=command,
        environment_contract=environment,
        factory_sources=factory_sources,
        requirement_inputs=(requirement,),
        governance_inputs=(governance,),
        governance_snapshot=snapshot,
        execution_fingerprint=fingerprint,
        expected_output_paths=(OUTPUT_PATH,),
        limitations=(
            "External payment ecosystems are not exercised; the requirement contract "
            "keeps real payment calls disabled.",
            "Network isolation and absence of latent network-capable code are not "
            "measured by this scenario.",
            "The declared source checkout is used through PYTHONPATH; this is not "
            "clean-room reconstruction proof.",
            "This evidence does not prove deployment, production readiness, "
            "certification, regulatory approval, security assurance, or performance.",
        ),
    )


def _check(
    check_id: str,
    passed: bool,
    expected: Any,
    observed: Any,
    explanation: str,
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id=check_id,
        status=AcceptanceStatus.PASS if passed else AcceptanceStatus.FAIL,
        expected=expected,
        observed=observed,
        explanation=explanation,
    )


def _blocked_check(
    check_id: str, expected: Any, observed: Any, explanation: str
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id=check_id,
        status=AcceptanceStatus.BLOCKED,
        expected=expected,
        observed=observed,
        explanation=explanation,
    )


def _workspace_is_isolated(project_root: Path, workspace_root: Path) -> bool:
    project = project_root.resolve()
    workspace = workspace_root.resolve()
    return (
        workspace != project
        and project not in workspace.parents
        and workspace not in project.parents
        and not workspace_root.is_symlink()
    )


def _environment_observation() -> dict[str, Any]:
    try:
        executable_sha256: str | None = _sha256_file(Path(sys.executable))
    except OSError:
        executable_sha256 = None
    return {
        "external_system_calls": "NOT_MEASURED",
        "network_isolation": "NOT_YET_MEASURED",
        "python_executable_sha256": executable_sha256,
        "python_implementation": platform.python_implementation(),
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        ),
        "required_environment": {
            "FACTORY_LLM_ENABLED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
            "REAL_PAYMENT_CALLS": "disabled",
        },
        "workspace": "CALLER_OWNED_NEW_EMPTY_DISPOSABLE_WORKSPACE",
    }


def _blocked_result(
    checks: Iterable[AcceptanceCheck], scenario: OperationalAcceptanceScenario
) -> OperationalAcceptanceResult:
    return OperationalAcceptanceResult(
        status=AcceptanceStatus.BLOCKED,
        command_executed=False,
        exit_code=None,
        checks=tuple(checks),
        output_artifacts=(),
        stdout_sha256=None,
        stderr_sha256=None,
        environment_observation=_environment_observation(),
        limitations=(
            *scenario.limitations,
            "The representative workflow was not executed because one or more "
            "prerequisites were unavailable or unsafe.",
        ),
    )


def _prerequisite_checks(
    scenario: OperationalAcceptanceScenario,
    project_root: Path,
    workspace_root: Path,
) -> tuple[AcceptanceCheck, ...]:
    checks: list[AcceptanceCheck] = []
    root_ok = project_root.is_dir()
    checks.append(
        AcceptanceCheck(
            "PREREQUISITE-SOURCE-CHECKOUT",
            AcceptanceStatus.PASS if root_ok else AcceptanceStatus.BLOCKED,
            "DECLARED_SOURCE_CHECKOUT_PRESENT",
            "PRESENT" if root_ok else "MISSING",
            "The supported entrypoint must come from the declared source checkout.",
        )
    )
    groups = (
        ("PREREQUISITE-FACTORY-SOURCES", scenario.factory_sources),
        ("PREREQUISITE-REQUIREMENT-INPUTS", scenario.requirement_inputs),
        ("PREREQUISITE-GOVERNANCE-INPUTS", scenario.governance_inputs),
    )
    for check_id, artifacts in groups:
        missing = [
            item.logical_path
            for item in artifacts
            if item.availability is ArtifactAvailability.MISSING
        ]
        checks.append(
            AcceptanceCheck(
                check_id,
                AcceptanceStatus.PASS if not missing else AcceptanceStatus.BLOCKED,
                [],
                missing,
                "All declared identities must resolve before execution.",
            )
        )
    checks.append(
        AcceptanceCheck(
            "PREREQUISITE-GOVERNANCE-SNAPSHOT",
            (
                AcceptanceStatus.PASS
                if scenario.governance_snapshot is not None
                else AcceptanceStatus.BLOCKED
            ),
            "PROVENANCE_BOUND_SNAPSHOT",
            (
                "BOUND"
                if scenario.governance_snapshot is not None
                else "MISSING_OR_INVALID"
            ),
            "The run must bind a parseable immutable governance snapshot.",
        )
    )
    python_ok = sys.version_info >= (3, 10)
    checks.append(
        AcceptanceCheck(
            "PREREQUISITE-PYTHON",
            AcceptanceStatus.PASS if python_ok else AcceptanceStatus.BLOCKED,
            "CPYTHON_3_10_OR_NEWER",
            (
                f"{platform.python_implementation().upper()}_"
                f"{sys.version_info.major}_{sys.version_info.minor}"
            ),
            "The supported compiler contract requires Python 3.10 or newer.",
        )
    )
    isolated = _workspace_is_isolated(project_root, workspace_root)
    try:
        empty = not workspace_root.exists() or (
            workspace_root.is_dir() and not any(workspace_root.iterdir())
        )
        workspace_observable = True
    except OSError:
        empty = False
        workspace_observable = False
    checks.append(
        AcceptanceCheck(
            "PREREQUISITE-DISPOSABLE-WORKSPACE",
            (
                AcceptanceStatus.PASS
                if isolated and empty
                else AcceptanceStatus.BLOCKED
            ),
            {"empty": True, "isolated_from_source": True, "symlink": False},
            {
                "empty": empty,
                "isolated_from_source": isolated,
                "observable": workspace_observable,
                "symlink": workspace_root.is_symlink(),
            },
            "Execution may write only to a new empty workspace outside the source checkout.",
        )
    )
    return tuple(checks)


def _load_output(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, type(exc).__name__
    if not isinstance(loaded, dict):
        return None, "JSON_ROOT_NOT_OBJECT"
    return loaded, None


def _output_checks(
    *,
    completed: subprocess.CompletedProcess[str] | None,
    process_error: str | None,
    output: dict[str, Any] | None,
    output_error: str | None,
    requirement: ArtifactIdentity,
) -> tuple[AcceptanceCheck, ...]:
    exit_code = completed.returncode if completed is not None else None
    checks: list[AcceptanceCheck] = [
        _check(
            "EXECUTION-COMPLETED",
            completed is not None,
            "COMPLETED_WITHIN_60_SECONDS",
            "COMPLETED" if completed is not None else process_error,
            "The supported entrypoint must complete without a harness exception or timeout.",
        ),
        _check(
            "EXECUTION-EXIT-CODE",
            exit_code == 0,
            0,
            exit_code,
            "The compiler validation command must return success.",
        ),
        _check(
            "OUTPUT-JSON-OBJECT",
            output is not None,
            "VALID_JSON_OBJECT",
            "VALID_JSON_OBJECT" if output is not None else output_error,
            "The expected requirements IR artifact must be readable structured data.",
        ),
    ]
    if output is None:
        return tuple(checks)

    canonical_hash = output.get("canonical_hash")
    canonical_subject = {
        key: value
        for key, value in output.items()
        if key not in {"canonical_hash", "diagnostics"}
    }
    calculated_hash = canonical_sha256(canonical_subject)
    checks.append(
        _check(
            "OUTPUT-CANONICAL-HASH",
            canonical_hash == calculated_hash,
            calculated_hash,
            canonical_hash,
            "The output must bind its canonical requirement content exactly.",
        )
    )
    application = output.get("application", {})
    checks.append(
        _check(
            "OUTPUT-APPLICATION-IDENTITY",
            isinstance(application, Mapping)
            and application.get("app_id") == "upi_app_factory"
            and application.get("product_name") == "UPI App Factory"
            and application.get("repository_id") == "upi_app_factory",
            {
                "app_id": "upi_app_factory",
                "product_name": "UPI App Factory",
                "repository_id": "upi_app_factory",
            },
            (
                {
                    key: application.get(key)
                    for key in ("app_id", "product_name", "repository_id")
                }
                if isinstance(application, Mapping)
                else "INVALID_APPLICATION_OBJECT"
            ),
            "The compiled IR must preserve canonical factory identity.",
        )
    )
    checks.append(
        _check(
            "OUTPUT-MOCK-SAFETY-BOUNDARY",
            isinstance(application, Mapping)
            and application.get("real_payment_calls") == "disabled"
            and application.get("runtime_llm_calls_default") == 0
            and application.get("data_policy") == "fictional_only",
            {
                "data_policy": "fictional_only",
                "real_payment_calls": "disabled",
                "runtime_llm_calls_default": 0,
            },
            (
                {
                    key: application.get(key)
                    for key in (
                        "data_policy",
                        "real_payment_calls",
                        "runtime_llm_calls_default",
                    )
                }
                if isinstance(application, Mapping)
                else "INVALID_APPLICATION_OBJECT"
            ),
            "The representative UPI workflow remains fictional, local, and mock-safe.",
        )
    )
    documents = output.get("source_documents", [])
    source_hashes = {
        item.get("sha256")
        for item in documents
        if isinstance(item, Mapping) and isinstance(item.get("sha256"), str)
    }
    checks.append(
        _check(
            "OUTPUT-REQUIREMENT-INPUT-BINDING",
            requirement.sha256 is not None and requirement.sha256 in source_hashes,
            requirement.sha256,
            sorted(source_hashes),
            "The compiled IR must identify the exact copied requirement input bytes.",
        )
    )
    traceability = output.get("traceability")
    traceability_valid = (
        isinstance(traceability, list)
        and bool(traceability)
        and all(
            isinstance(item, Mapping)
            and isinstance(item.get("requirement_id"), str)
            and _is_sha256(item.get("canonical_hash"))
            for item in traceability
        )
    )
    checks.append(
        _check(
            "OUTPUT-TRACEABILITY",
            traceability_valid,
            "NONEMPTY_ROWS_WITH_REQUIREMENT_ID_AND_SHA256",
            len(traceability) if isinstance(traceability, list) else "INVALID",
            "Maintainers must be able to trace compiled requirements to stable rows.",
        )
    )
    diagnostics = output.get("diagnostics", [])
    blockers = sorted(
        str(item.get("code"))
        for item in diagnostics
        if isinstance(item, Mapping) and item.get("severity") in {"critical", "error"}
    ) if isinstance(diagnostics, list) else ["INVALID_DIAGNOSTICS"]
    checks.append(
        _check(
            "OUTPUT-BLOCKING-DIAGNOSTICS",
            not blockers,
            [],
            blockers,
            "Critical and error diagnostics fail operational acceptance closed.",
        )
    )
    return tuple(checks)


def run_representative_operational_acceptance(
    project_root: Path, workspace_root: Path
) -> OperationalAcceptanceEvidence:
    """Execute the real compiler scenario and return canonical machine evidence."""
    root = project_root.resolve()
    scenario = build_representative_scenario(root)
    prerequisite_checks = _prerequisite_checks(scenario, root, workspace_root)
    if any(item.status is AcceptanceStatus.BLOCKED for item in prerequisite_checks):
        return OperationalAcceptanceEvidence(
            scenario, _blocked_result(prerequisite_checks, scenario)
        )

    try:
        workspace_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        # An existing empty directory was already accepted by the prerequisite gate.
        pass
    except OSError:
        blocked = (
            *prerequisite_checks,
            _blocked_check(
                "PREREQUISITE-WORKSPACE-CREATION",
                "WRITABLE",
                "UNAVAILABLE",
                "The disposable workspace could not be created.",
            ),
        )
        return OperationalAcceptanceEvidence(scenario, _blocked_result(blocked, scenario))

    input_path = workspace_root / COPIED_INPUT_PATH
    output_path = workspace_root / OUTPUT_PATH
    try:
        input_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / REQUIREMENT_PATH, input_path)
    except OSError:
        blocked = (
            *prerequisite_checks,
            _blocked_check(
                "PREREQUISITE-INPUT-STAGING",
                "EXACT_INPUT_COPY_AVAILABLE",
                "UNAVAILABLE",
                "The exact requirement input could not be staged in the disposable workspace.",
            ),
        )
        return OperationalAcceptanceEvidence(scenario, _blocked_result(blocked, scenario))

    copied_digest = _sha256_file(input_path)
    requirement = scenario.requirement_inputs[0]
    if copied_digest != requirement.sha256:
        blocked = (
            *prerequisite_checks,
            _blocked_check(
                "PREREQUISITE-INPUT-STAGING-IDENTITY",
                requirement.sha256,
                copied_digest,
                "Staged requirement bytes do not match the declared input identity.",
            ),
        )
        return OperationalAcceptanceEvidence(scenario, _blocked_result(blocked, scenario))

    actual_argv = [sys.executable, *scenario.command.argv[1:]]
    environment = {
        "FACTORY_LLM_ENABLED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(root),
        "PYTHONUTF8": "1",
        "REAL_PAYMENT_CALLS": "disabled",
    }
    completed: subprocess.CompletedProcess[str] | None = None
    process_error: str | None = None
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            actual_argv,
            cwd=workspace_root,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
        )
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        process_error = "TIMEOUT"
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    except OSError as exc:
        process_error = type(exc).__name__

    if completed is None and process_error != "TIMEOUT":
        blocked = (
            *prerequisite_checks,
            _blocked_check(
                "PREREQUISITE-INTERPRETER-EXECUTION",
                "EXECUTABLE",
                process_error,
                "The bound current interpreter could not start the supported entrypoint.",
            ),
        )
        return OperationalAcceptanceEvidence(scenario, _blocked_result(blocked, scenario))

    output, output_error = _load_output(output_path)
    execution_checks = _output_checks(
        completed=completed,
        process_error=process_error,
        output=output,
        output_error=output_error,
        requirement=requirement,
    )
    checks = (*prerequisite_checks, *execution_checks)
    status = (
        AcceptanceStatus.PASS
        if all(item.status is AcceptanceStatus.PASS for item in checks)
        else AcceptanceStatus.FAIL
    )
    artifacts = tuple(
        ArtifactIdentity.observe(workspace_root, path, ArtifactRole.EXECUTION_OUTPUT)
        for path in scenario.expected_output_paths
    )
    result = OperationalAcceptanceResult(
        status=status,
        command_executed=True,
        exit_code=completed.returncode if completed is not None else None,
        checks=checks,
        output_artifacts=artifacts,
        stdout_sha256=_sha256_bytes(stdout.encode("utf-8")),
        stderr_sha256=_sha256_bytes(stderr.encode("utf-8")),
        environment_observation=_environment_observation(),
        limitations=(
            *scenario.limitations,
            "The result covers only the declared requirements-compiler scenario and "
            "exact bound inputs.",
        ),
    )
    return OperationalAcceptanceEvidence(scenario, result)


def write_operational_acceptance_evidence(
    evidence: OperationalAcceptanceEvidence, path: Path
) -> dict[str, str]:
    """Write canonical JSON without adding timestamps or local paths to the record."""
    if not isinstance(evidence, OperationalAcceptanceEvidence):
        raise OperationalAcceptanceError(
            "evidence must use OperationalAcceptanceEvidence"
        )
    if path.exists():
        raise OperationalAcceptanceError(
            "evidence output already exists; use a new disposable output path"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (evidence.to_json() + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return {
        "evidence_id": evidence.evidence_id,
        "file_sha256": _sha256_bytes(encoded),
        "status": evidence.result.status.value,
    }


def _validate_identity_record(
    value: Mapping[str, Any], *, id_field: str, digest_field: str, prefix: str
) -> None:
    digest = value.get(digest_field)
    identity = value.get(id_field)
    if not _is_sha256(digest) or identity != f"{prefix}{digest}":
        raise OperationalAcceptanceError(f"{id_field} is invalid")
    core = {
        key: item
        for key, item in value.items()
        if key not in {id_field, digest_field}
    }
    if canonical_sha256(core) != digest:
        raise OperationalAcceptanceError(f"{digest_field} is invalid")


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def validate_operational_acceptance_evidence(document: Mapping[str, Any]) -> bool:
    """Fail closed on tampering, unstable time fields, or self-awarded authority."""
    if not isinstance(document, Mapping):
        raise OperationalAcceptanceError("evidence document must be a JSON object")
    value = cast(dict[str, Any], json.loads(canonical_json(dict(document))))
    expected_fields = {
        "authority_boundary",
        "evidence_id",
        "evidence_sha256",
        "identity_scope",
        "limitations",
        "provenance",
        "result",
        "scenario",
        "schema_version",
    }
    if set(value) != expected_fields:
        raise OperationalAcceptanceError("evidence document fields are invalid")
    if value.get("schema_version") != OperationalAcceptanceEvidence.SCHEMA_VERSION:
        raise OperationalAcceptanceError("evidence schema version is unsupported")
    if value.get("identity_scope") != "CANONICAL_EVIDENCE_CORE":
        raise OperationalAcceptanceError("evidence identity scope is invalid")
    forbidden_time_keys = {
        "created_at",
        "generated_at",
        "timestamp",
        "updated_at",
        "wall_clock_time",
    }
    if forbidden_time_keys.intersection(_walk_keys(value)):
        raise OperationalAcceptanceError(
            "wall-clock fields must not destabilize operational evidence identity"
        )
    authority = value.get("authority_boundary")
    if authority != {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
        "self_awarded_readiness": False,
    }:
        raise OperationalAcceptanceError("authority boundary is invalid")
    scenario = value.get("scenario")
    result = value.get("result")
    provenance = value.get("provenance")
    if not all(isinstance(item, Mapping) for item in (scenario, result, provenance)):
        raise OperationalAcceptanceError(
            "scenario, result, and provenance must be objects"
        )
    scenario_value = cast(Mapping[str, Any], scenario)
    result_value = cast(Mapping[str, Any], result)
    provenance_value = cast(Mapping[str, Any], provenance)
    if (
        scenario_value.get("schema_version")
        != OperationalAcceptanceScenario.SCHEMA_VERSION
    ):
        raise OperationalAcceptanceError("scenario schema version is unsupported")
    if result_value.get("schema_version") != OperationalAcceptanceResult.SCHEMA_VERSION:
        raise OperationalAcceptanceError("result schema version is unsupported")
    _validate_identity_record(
        scenario_value,
        id_field="scenario_id",
        digest_field="scenario_sha256",
        prefix="OPERATIONAL-ACCEPTANCE-SCENARIO-",
    )
    _validate_identity_record(
        result_value,
        id_field="result_id",
        digest_field="result_sha256",
        prefix="OPERATIONAL-ACCEPTANCE-RESULT-",
    )
    fingerprint = scenario_value.get("execution_fingerprint")
    if not isinstance(fingerprint, Mapping):
        raise OperationalAcceptanceError("execution fingerprint is missing")
    _validate_identity_record(
        fingerprint,
        id_field="fingerprint_id",
        digest_field="fingerprint_sha256",
        prefix="EXECUTION-FINGERPRINT-",
    )
    status = result_value.get("status")
    try:
        typed_status = AcceptanceStatus(status)
    except (TypeError, ValueError) as exc:
        raise OperationalAcceptanceError("result status is invalid") from exc
    checks = result_value.get("checks")
    if not isinstance(checks, list) or not checks:
        raise OperationalAcceptanceError("evidence requires result checks")
    try:
        check_statuses = [
            AcceptanceStatus(item.get("status"))
            for item in checks
            if isinstance(item, Mapping)
        ]
    except (TypeError, ValueError) as exc:
        raise OperationalAcceptanceError("check status is invalid") from exc
    if len(check_statuses) != len(checks):
        raise OperationalAcceptanceError("result checks must be objects")
    executed = result_value.get("command_executed")
    exit_code = result_value.get("exit_code")
    if typed_status is AcceptanceStatus.PASS and not (
        executed is True
        and exit_code == 0
        and all(item is AcceptanceStatus.PASS for item in check_statuses)
    ):
        raise OperationalAcceptanceError("PASS is not derived from passing evidence")
    if typed_status is AcceptanceStatus.FAIL and not (
        executed is True and AcceptanceStatus.FAIL in check_statuses
    ):
        raise OperationalAcceptanceError("FAIL is not derived from failed evidence")
    if typed_status is AcceptanceStatus.BLOCKED and not (
        executed is False
        and exit_code is None
        and AcceptanceStatus.BLOCKED in check_statuses
    ):
        raise OperationalAcceptanceError("BLOCKED is not derived from prerequisites")
    if typed_status is AcceptanceStatus.NOT_APPLICABLE and executed is not False:
        raise OperationalAcceptanceError("NOT_APPLICABLE cannot execute the scenario")
    output_artifacts = result_value.get("output_artifacts")
    if not isinstance(output_artifacts, list):
        raise OperationalAcceptanceError("output artifacts must be a list")
    for artifact in output_artifacts:
        if not isinstance(artifact, Mapping):
            raise OperationalAcceptanceError("output artifact identity is invalid")
        path = artifact.get("logical_path")
        if not isinstance(path, str):
            raise OperationalAcceptanceError("output artifact path is invalid")
        _logical_path(path, "output artifact path")
        if artifact.get("role") != ArtifactRole.EXECUTION_OUTPUT.value:
            raise OperationalAcceptanceError("output artifact role is invalid")
        availability = artifact.get("availability")
        if availability == ArtifactAvailability.PRESENT.value:
            if not _is_sha256(artifact.get("sha256")):
                raise OperationalAcceptanceError("output artifact digest is invalid")
        elif availability != ArtifactAvailability.MISSING.value:
            raise OperationalAcceptanceError("output artifact availability is invalid")
    evidence_digest = value.get("evidence_sha256")
    core = {
        key: item
        for key, item in value.items()
        if key not in {"evidence_id", "evidence_sha256", "provenance"}
    }
    if not _is_sha256(evidence_digest) or canonical_sha256(core) != evidence_digest:
        raise OperationalAcceptanceError("evidence digest is invalid")
    if value.get("evidence_id") != f"OPERATIONAL-ACCEPTANCE-EVIDENCE-{evidence_digest}":
        raise OperationalAcceptanceError("evidence ID is invalid")
    expected_provenance = ProvenanceBinding(
        source_id=f"SOURCE-OPERATIONAL-ACCEPTANCE-{evidence_digest}",
        revision=str(fingerprint.get("fingerprint_id")),
        content_sha256=cast(str, evidence_digest),
        source_type="MACHINE_EXECUTION_RECORD",
    ).to_dict()
    if dict(provenance_value) != expected_provenance:
        raise OperationalAcceptanceError("evidence provenance is invalid")
    return True


# Concise aliases retain the stage vocabulary without creating another model.
AcceptanceScenario = OperationalAcceptanceScenario
AcceptanceResult = OperationalAcceptanceResult
AcceptanceEvidence = OperationalAcceptanceEvidence
OperationalAcceptanceStatus = AcceptanceStatus
run_operational_acceptance = run_representative_operational_acceptance
validate_operational_acceptance_document = validate_operational_acceptance_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic local operational acceptance evidence."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    evidence = run_representative_operational_acceptance(
        parsed.project_root, parsed.workspace
    )
    if evidence.result.status is AcceptanceStatus.BLOCKED:
        print(
            canonical_json(
                {
                    "evidence_artifact": "NOT_WRITTEN_BLOCKED",
                    "evidence_id": evidence.evidence_id,
                    "status": evidence.result.status.value,
                }
            )
        )
        return 2
    output_path = parsed.evidence_output or (
        parsed.workspace / "operational_acceptance_evidence.json"
    )
    summary = write_operational_acceptance_evidence(evidence, output_path)
    summary["evidence_artifact"] = (
        output_path.relative_to(parsed.workspace).as_posix()
        if output_path.is_relative_to(parsed.workspace)
        else "CALLER_SELECTED_OUTPUT"
    )
    print(canonical_json(summary))
    if evidence.result.status in {
        AcceptanceStatus.PASS,
        AcceptanceStatus.NOT_APPLICABLE,
    }:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
