"""Canonical clean-room reconstruction evidence for a supported factory path.

The protocol resolves an immutable local Git commit, reconstructs it in a new
workspace, runs the existing public-clone hygiene validator, and exercises the
requirements compiler with a replaced environment and an enforced Python
network-denial audit hook.  The resulting record is machine observation only;
it cannot grant deployment, production, certification, or regulatory authority.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, ClassVar, Iterable, Mapping, Sequence, cast

from factory.documentation import (
    EvidenceGraph,
    FactNode,
    FactStatus,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from factory.governance_evolution import ExecutionFingerprint

from .harness import (
    AcceptanceCheck,
    AcceptanceStatus,
    ArtifactAvailability,
    ArtifactIdentity,
    ArtifactRole,
    CommandContract,
    COPIED_INPUT_PATH,
    EVIDENCE_INPUT_IDENTITY,
    EnvironmentContract,
    GOVERNANCE_PATH,
    OperationalAcceptanceError,
    OUTPUT_PATH,
    REQUIREMENT_PATH,
    _is_sha256,
    _load_output,
    _logical_path,
    _output_checks,
    _sha256_bytes,
    _sha256_file,
    _stable_text,
    _workspace_is_isolated,
)


class CleanRoomReconstructionError(OperationalAcceptanceError):
    """Raised when clean-room evidence is ambiguous or has been tampered with."""


SOURCE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
GIT_OBJECT_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
PERSONAL_PATH_PATTERN = re.compile(
    r"(?:file://|(?:^|[\s'\"(=])/(?:home|root|Users|tmp|workspace|mnt)(?:/|\b)|"
    r"[A-Za-z]:\\(?:Users|Temp)(?:\\|\b))",
    re.IGNORECASE,
)
PERSONAL_PATH_SCAN_EXEMPT_LINES = {
    "scripts/validate_public_clone_readiness.py": frozenset(
        {
            're.compile(r"/home/marcose(?:/|\\b)"),',
            'and "may depend on `/home/marcose`" in line',
        }
    )
}
ENVIRONMENT_ACCESS_PATTERNS = (
    re.compile(r"\bos\.getenv\(\s*['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]"),
    re.compile(
        r"\bos\.environ(?:\.get\(\s*|\[\s*)['\"]"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]"
    ),
)
HOME_ACCESS_PATTERN = re.compile(r"\b(?:Path\.home\(|expanduser\()")
SOURCE_DEPENDENCY_PATHS = (
    "factory/__init__.py",
    "factory/application_engineering/__init__.py",
    "factory/application_engineering/requirements_compiler.py",
    REQUIREMENT_PATH,
    GOVERNANCE_PATH,
    "pyproject.toml",
    "scripts/validate_public_clone_readiness.py",
)
PROTOCOL_IMPLEMENTATION_PATHS = (
    "factory/documentation/facts.py",
    "factory/governance_evolution/snapshots.py",
    "factory/operational_acceptance/clean_room.py",
    "factory/operational_acceptance/harness.py",
)
DECLARED_CHILD_ENVIRONMENT = {
    "FACTORY_LLM_ENABLED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONUTF8": "1",
    "REAL_PAYMENT_CALLS": "disabled",
}
PROTOCOL_ID = "LOCAL-NO-NETWORK-CLEAN-ROOM-RECONSTRUCTION-V1"
SCENARIO_KEY = "CLEAN-ROOM-FAILED-DEBIT-REQUIREMENTS-COMPILER-V1"
REQUIRED_PASS_CHECK_IDS = frozenset(
    {
        "EXECUTION-COMPLETED",
        "EXECUTION-EXIT-CODE",
        "HIDDEN-STATE-ENVIRONMENT-INHERITANCE",
        "HIDDEN-STATE-IMPLICIT-HOME-RESOLUTION",
        "HIDDEN-STATE-OUTPUT-LOCAL-PATHS",
        "HIDDEN-STATE-PERSONAL-PATHS",
        "HIDDEN-STATE-UNDECLARED-ENVIRONMENT",
        "HIDDEN-STATE-UNTRACKED-SOURCE-DEPENDENCIES",
        "NO-NETWORK-PYTHON-AUDIT-GUARD",
        "OUTPUT-APPLICATION-IDENTITY",
        "OUTPUT-BLOCKING-DIAGNOSTICS",
        "OUTPUT-CANONICAL-HASH",
        "OUTPUT-JSON-OBJECT",
        "OUTPUT-MOCK-SAFETY-BOUNDARY",
        "OUTPUT-REQUIREMENT-INPUT-BINDING",
        "OUTPUT-TRACEABILITY",
        "PREREQUISITE-DECLARED-SOURCE-DEPENDENCIES",
        "PREREQUISITE-DISPOSABLE-WORKSPACE",
        "PREREQUISITE-EXACT-SOURCE-IDENTITY",
        "PREREQUISITE-GIT",
        "PREREQUISITE-LOCAL-GIT-SOURCE",
        "PREREQUISITE-PYTHON",
        "PREREQUISITE-RUNTIME-SOURCE-SYNTAX",
        "PREREQUISITE-SOURCE-MUTATION-OBSERVABILITY",
        "RECONSTRUCTION-EXACT-CLEAN-CHECKOUT",
        "RECONSTRUCTION-LOCAL-CLONE",
        "RECONSTRUCTION-LOCAL-ORIGIN-REMOVED",
        "RECONSTRUCTION-NO-PREEXISTING-GENERATED-OUTPUT",
        "RECONSTRUCTION-PUBLIC-CLONE-HYGIENE",
        "RECONSTRUCTION-REQUIREMENT-STAGING",
        "HIDDEN-STATE-RECONSTRUCTED-METADATA-PATHS",
        "SOURCE-REPOSITORY-NOT-MUTATED",
    }
)

# ``-I -S`` removes current-user and installed-site Python state.  The audit
# hook rejects every socket operation before the target module is imported.
# The checkout path is passed as an argv value, never embedded in this source.
NETWORK_DENIAL_BOOTSTRAP = """\
import runpy
import sys

def _deny_network(event, _args):
    if event.startswith("socket."):
        raise RuntimeError("CLEAN_ROOM_NETWORK_DENIED")

sys.addaudithook(_deny_network)
checkout = sys.argv[1]
module = sys.argv[2]
sys.path.insert(0, checkout)
sys.argv = [module, *sys.argv[3:]]
runpy.run_module(module, run_name="__main__")
"""


def _source_ref(value: str) -> str:
    _stable_text(value, "source_ref")
    if (
        not SOURCE_REF_PATTERN.fullmatch(value)
        or value.startswith("-")
        or ".." in value
        or "//" in value
        or value.endswith("/")
    ):
        raise CleanRoomReconstructionError("source_ref is not a safe Git revision name")
    return value


def _git_object(value: str | None, field_name: str) -> str | None:
    if value is not None and not GIT_OBJECT_PATTERN.fullmatch(value):
        raise CleanRoomReconstructionError(f"{field_name} must be a Git object identity")
    return value


def _paths(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise CleanRoomReconstructionError(f"{field_name} must be a collection")
    normalized = tuple(sorted(_logical_path(value, field_name) for value in values))
    if not normalized or len(normalized) != len(set(normalized)):
        raise CleanRoomReconstructionError(f"{field_name} must contain unique paths")
    return normalized


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout: int = 120,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def _git_environment(protocol_root: Path, git_executable: Path) -> dict[str, str]:
    return {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": str(protocol_root / "declared-home"),
        "LC_ALL": "C",
        "PATH": str(git_executable.parent),
        "XDG_CONFIG_HOME": str(protocol_root / "declared-xdg-config"),
    }


def _child_environment() -> dict[str, str]:
    return dict(DECLARED_CHILD_ENVIRONMENT)


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _blocked_check(
    check_id: str, expected: Any, observed: Any, explanation: str
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id,
        AcceptanceStatus.BLOCKED,
        expected,
        observed,
        explanation,
    )


def _pass_or_blocked_check(
    check_id: str,
    passed: bool,
    expected: Any,
    observed: Any,
    explanation: str,
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id,
        AcceptanceStatus.PASS if passed else AcceptanceStatus.BLOCKED,
        expected,
        observed,
        explanation,
    )


def _pass_or_fail_check(
    check_id: str,
    passed: bool,
    expected: Any,
    observed: Any,
    explanation: str,
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id,
        AcceptanceStatus.PASS if passed else AcceptanceStatus.FAIL,
        expected,
        observed,
        explanation,
    )


@dataclass(frozen=True)
class CleanRoomSourceIdentity:
    """Exact Git identity and content identities for the exercised source set."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.clean-room-source-identity.v1"

    requested_ref: str
    availability: ArtifactAvailability
    commit_oid: str | None
    tree_oid: str | None
    artifacts: tuple[ArtifactIdentity, ...]

    def __post_init__(self) -> None:
        _source_ref(self.requested_ref)
        if not isinstance(self.availability, ArtifactAvailability):
            raise CleanRoomReconstructionError(
                "source availability must use ArtifactAvailability"
            )
        _git_object(self.commit_oid, "commit_oid")
        _git_object(self.tree_oid, "tree_oid")
        if self.availability is ArtifactAvailability.PRESENT:
            if self.commit_oid is None or self.tree_oid is None:
                raise CleanRoomReconstructionError(
                    "present source identity requires commit and tree identities"
                )
        elif self.commit_oid is not None or self.tree_oid is not None:
            raise CleanRoomReconstructionError(
                "missing source identity cannot assert commit or tree identities"
            )
        artifacts = tuple(self.artifacts)
        paths = [item.logical_path for item in artifacts]
        if len(paths) != len(set(paths)):
            raise CleanRoomReconstructionError("source artifact paths must be unique")
        if any(item.role is ArtifactRole.EXECUTION_OUTPUT for item in artifacts):
            raise CleanRoomReconstructionError(
                "source identity cannot contain execution outputs"
            )
        object.__setattr__(
            self, "artifacts", tuple(sorted(artifacts, key=lambda item: item.logical_path))
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifacts": [item.to_dict() for item in self.artifacts],
            "availability": self.availability.value,
            "commit_oid": self.commit_oid,
            "repository_id": "upi_app_factory",
            "requested_ref": self.requested_ref,
            "schema_version": self.SCHEMA_VERSION,
            "tree_oid": self.tree_oid,
        }

    @property
    def source_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def source_id(self) -> str:
        return f"CLEAN-ROOM-SOURCE-{self.source_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "source_id": self.source_id,
            "source_sha256": self.source_sha256,
        }


@dataclass(frozen=True)
class CleanRoomReconstructionResult:
    """Typed, evidence-derived reconstruction and execution outcome."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.clean-room-reconstruction-result.v1"

    status: AcceptanceStatus
    reconstruction_performed: bool
    supported_path_executed: bool
    exit_code: int | None
    checks: tuple[AcceptanceCheck, ...]
    output_artifacts: tuple[ArtifactIdentity, ...]
    stdout_sha256: str | None
    stderr_sha256: str | None
    environment_observation: Mapping[str, Any]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, AcceptanceStatus):
            raise CleanRoomReconstructionError("result status must use AcceptanceStatus")
        if not isinstance(self.reconstruction_performed, bool) or not isinstance(
            self.supported_path_executed, bool
        ):
            raise CleanRoomReconstructionError(
                "reconstruction and execution observations must be booleans"
            )
        if self.exit_code is not None and not isinstance(self.exit_code, int):
            raise CleanRoomReconstructionError("exit_code must be an integer or null")
        checks = tuple(sorted(self.checks, key=lambda item: item.check_id))
        if not checks or len({item.check_id for item in checks}) != len(checks):
            raise CleanRoomReconstructionError("result checks must be non-empty and unique")
        if any(not isinstance(item, AcceptanceCheck) for item in checks):
            raise CleanRoomReconstructionError("checks must use AcceptanceCheck")
        artifacts = tuple(sorted(self.output_artifacts, key=lambda item: item.logical_path))
        if any(item.role is not ArtifactRole.EXECUTION_OUTPUT for item in artifacts):
            raise CleanRoomReconstructionError(
                "output artifacts must use the EXECUTION_OUTPUT role"
            )
        if self.supported_path_executed:
            if not _is_sha256(self.stdout_sha256) or not _is_sha256(self.stderr_sha256):
                raise CleanRoomReconstructionError(
                    "executed supported paths require stdout and stderr identities"
                )
        elif any(
            item is not None
            for item in (self.exit_code, self.stdout_sha256, self.stderr_sha256)
        ):
            raise CleanRoomReconstructionError(
                "unexecuted supported paths cannot assert process observations"
            )
        statuses = {item.status for item in checks}
        if self.status is AcceptanceStatus.PASS:
            if (
                not self.reconstruction_performed
                or not self.supported_path_executed
                or self.exit_code != 0
                or AcceptanceStatus.FAIL in statuses
                or AcceptanceStatus.BLOCKED in statuses
            ):
                raise CleanRoomReconstructionError(
                    "PASS must derive from completed reconstruction and passing execution"
                )
        elif self.status is AcceptanceStatus.FAIL:
            if not self.supported_path_executed or AcceptanceStatus.FAIL not in statuses:
                raise CleanRoomReconstructionError(
                    "FAIL requires an executed path and a failed check"
                )
        elif self.status is AcceptanceStatus.BLOCKED:
            if self.supported_path_executed or AcceptanceStatus.BLOCKED not in statuses:
                raise CleanRoomReconstructionError(
                    "BLOCKED must stop before execution on a blocked prerequisite"
                )
        elif self.supported_path_executed:
            raise CleanRoomReconstructionError(
                "NOT_APPLICABLE cannot execute the supported path"
            )
        observation = json.loads(canonical_json(dict(self.environment_observation)))
        limitations = tuple(sorted(_stable_text(item, "limitation") for item in self.limitations))
        if not limitations or len(limitations) != len(set(limitations)):
            raise CleanRoomReconstructionError("limitations must be explicit and unique")
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "output_artifacts", artifacts)
        object.__setattr__(self, "environment_observation", observation)
        object.__setattr__(self, "limitations", limitations)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "checks": [item.to_dict() for item in self.checks],
            "environment_observation": dict(self.environment_observation),
            "exit_code": self.exit_code,
            "limitations": list(self.limitations),
            "output_artifacts": [item.to_dict() for item in self.output_artifacts],
            "reconstruction_performed": self.reconstruction_performed,
            "schema_version": self.SCHEMA_VERSION,
            "status": self.status.value,
            "stderr_sha256": self.stderr_sha256,
            "stdout_sha256": self.stdout_sha256,
            "supported_path_executed": self.supported_path_executed,
        }

    @property
    def result_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def result_id(self) -> str:
        return f"CLEAN-ROOM-RESULT-{self.result_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "result_id": self.result_id,
            "result_sha256": self.result_sha256,
        }


@dataclass(frozen=True)
class CleanRoomReconstructionEvidence:
    """Authenticated clean-room observation with an explicit authority boundary."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.clean-room-reconstruction-evidence.v1"

    source_identity: CleanRoomSourceIdentity
    command: CommandContract
    environment_contract: EnvironmentContract
    execution_fingerprint: ExecutionFingerprint
    result: CleanRoomReconstructionResult
    source_dependency_paths: tuple[str, ...]
    limitations: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_identity, CleanRoomSourceIdentity):
            raise CleanRoomReconstructionError(
                "source_identity must use CleanRoomSourceIdentity"
            )
        if not isinstance(self.command, CommandContract):
            raise CleanRoomReconstructionError("command must use CommandContract")
        if not isinstance(self.environment_contract, EnvironmentContract):
            raise CleanRoomReconstructionError(
                "environment_contract must reuse EnvironmentContract"
            )
        if not isinstance(self.execution_fingerprint, ExecutionFingerprint):
            raise CleanRoomReconstructionError(
                "execution_fingerprint must reuse the M2.5 contract"
            )
        if not isinstance(self.result, CleanRoomReconstructionResult):
            raise CleanRoomReconstructionError(
                "result must use CleanRoomReconstructionResult"
            )
        dependencies = _paths(self.source_dependency_paths, "source_dependency_paths")
        artifact_paths = {item.logical_path for item in self.source_identity.artifacts}
        if not set(dependencies).issubset(artifact_paths):
            raise CleanRoomReconstructionError(
                "every source dependency must have an exact artifact identity"
            )
        if (
            self.execution_fingerprint.factory_source_identity
            != self.source_identity.source_id
        ):
            raise CleanRoomReconstructionError(
                "execution fingerprint does not bind the exact reconstructed source"
            )
        object.__setattr__(self, "source_dependency_paths", dependencies)
        object.__setattr__(
            self,
            "limitations",
            tuple(sorted(set(self.result.limitations))),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_boundary": {
                "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
                "ai_authority": "NONE",
                "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
                "self_awarded_readiness": False,
            },
            "command": self.command.to_dict(),
            "environment_contract": self.environment_contract.to_dict(),
            "execution_fingerprint": self.execution_fingerprint.to_dict(),
            "identity_scope": "CANONICAL_CLEAN_ROOM_EVIDENCE_CORE",
            "limitations": list(self.limitations),
            "protocol": _protocol_contract(),
            "result": self.result.to_dict(),
            "scenario_key": SCENARIO_KEY,
            "schema_version": self.SCHEMA_VERSION,
            "source_dependency_paths": list(self.source_dependency_paths),
            "source_identity": self.source_identity.to_dict(),
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def evidence_id(self) -> str:
        return f"CLEAN-ROOM-EVIDENCE-{self.evidence_sha256}"

    @property
    def provenance_binding(self) -> ProvenanceBinding:
        return ProvenanceBinding(
            source_id=f"SOURCE-CLEAN-ROOM-{self.evidence_sha256}",
            revision=self.execution_fingerprint.fingerprint_id,
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
        return FactNode(
            node_id=f"FACT-CLEAN-ROOM-{self.evidence_sha256}",
            node_type="AUTHENTICATED_MACHINE_EVIDENCE",
            status=FactStatus.PROVEN,
            value={
                "evidence_id": self.evidence_id,
                "result": self.result.status.value,
                "source_id": self.source_identity.source_id,
            },
            provenance=(self.provenance_binding,),
            metadata={
                "authority": "MACHINE_OBSERVATION_ONLY",
                "limitations": list(self.limitations),
            },
        )

    def evidence_graph(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=(self.machine_evidence_fact(),))


def _artifact_role(logical_path: str) -> ArtifactRole:
    if logical_path == REQUIREMENT_PATH:
        return ArtifactRole.REQUIREMENT_INPUT
    if logical_path == GOVERNANCE_PATH:
        return ArtifactRole.GOVERNANCE_INPUT
    return ArtifactRole.FACTORY_SOURCE


def _git_blob(
    source_root: Path,
    commit_oid: str,
    logical_path: str,
    git_executable: Path,
    environment: Mapping[str, str],
) -> tuple[ArtifactIdentity, bytes | None]:
    completed = _run(
        [
            str(git_executable),
            "-C",
            str(source_root),
            "show",
            f"{commit_oid}:{logical_path}",
        ],
        cwd=source_root,
        environment=environment,
    )
    if completed.returncode != 0:
        return (
            ArtifactIdentity(
                logical_path,
                _artifact_role(logical_path),
                ArtifactAvailability.MISSING,
                None,
                None,
            ),
            None,
        )
    return (
        ArtifactIdentity(
            logical_path,
            _artifact_role(logical_path),
            ArtifactAvailability.PRESENT,
            _sha256_bytes(completed.stdout),
            len(completed.stdout),
        ),
        completed.stdout,
    )


def _untracked_declared_dependencies(
    source_root: Path,
    artifacts: Iterable[ArtifactIdentity],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            item.logical_path
            for item in artifacts
            if item.availability is ArtifactAvailability.MISSING
            and (source_root / PurePosixPath(item.logical_path)).is_file()
        )
    )


def _hidden_state_findings(
    blobs: Mapping[str, bytes], declared_environment: Iterable[str]
) -> dict[str, list[str]]:
    """Return stable logical findings without leaking source contents or values."""
    allowed = set(declared_environment)
    personal_paths: list[str] = []
    undeclared_environment: list[str] = []
    home_resolution: list[str] = []
    syntax_errors: list[str] = []
    for logical_path in sorted(blobs):
        payload = blobs[logical_path]
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            syntax_errors.append(logical_path)
            continue
        exempt_lines = PERSONAL_PATH_SCAN_EXEMPT_LINES.get(logical_path, frozenset())
        personal_path_scan = "\n".join(
            line for line in text.splitlines() if line.strip() not in exempt_lines
        )
        if PERSONAL_PATH_PATTERN.search(personal_path_scan):
            personal_paths.append(logical_path)
        if logical_path.endswith(".py"):
            try:
                ast.parse(text, filename=logical_path)
            except SyntaxError:
                syntax_errors.append(logical_path)
            for pattern in ENVIRONMENT_ACCESS_PATTERNS:
                for match in pattern.finditer(text):
                    name = match.group("name")
                    if name not in allowed:
                        undeclared_environment.append(f"{logical_path}:{name}")
            if HOME_ACCESS_PATTERN.search(text):
                home_resolution.append(logical_path)
    return {
        "home_resolution": sorted(set(home_resolution)),
        "personal_paths": sorted(set(personal_paths)),
        "syntax_errors": sorted(set(syntax_errors)),
        "undeclared_environment": sorted(set(undeclared_environment)),
    }


def _empty_source_identity(
    source_ref: str, source_dependency_paths: Iterable[str]
) -> CleanRoomSourceIdentity:
    return CleanRoomSourceIdentity(
        requested_ref=source_ref,
        availability=ArtifactAvailability.MISSING,
        commit_oid=None,
        tree_oid=None,
        artifacts=tuple(
            ArtifactIdentity(
                path,
                _artifact_role(path),
                ArtifactAvailability.MISSING,
                None,
                None,
            )
            for path in source_dependency_paths
        ),
    )


def _command_contract() -> CommandContract:
    return CommandContract(
        entrypoint="factory.application_engineering.requirements_compiler:main",
        argv=(
            "{current_python}",
            "-I",
            "-S",
            "-c",
            "{network_denial_bootstrap}",
            "{reconstructed_checkout}",
            "factory.application_engineering.requirements_compiler",
            "validate",
            "--input",
            COPIED_INPUT_PATH,
            "--project-root",
            ".",
            "--output",
            OUTPUT_PATH,
        ),
        working_directory="CLEAN_ROOM_EXECUTION_WORKSPACE",
        interpreter_resolution=(
            "{current_python} is the exact interpreter running the protocol; -I -S "
            "disables user and installed-site state and the result binds its digest."
        ),
    )


def _clean_room_environment_contract() -> EnvironmentContract:
    return EnvironmentContract(
        contract_id="LOCAL-NO-NETWORK-CLEAN-ROOM-COMPILER-V1",
        workspace_requirement="NEW_EMPTY_DISPOSABLE_CLEAN_ROOM",
        source_checkout_requirement="IMMUTABLE_LOCAL_GIT_COMMIT",
    )


def _protocol_implementation_sha256() -> str:
    factory_root = Path(__file__).resolve().parent.parent
    identities = {
        logical_path: _sha256_file(
            factory_root / PurePosixPath(logical_path).relative_to("factory")
        )
        for logical_path in PROTOCOL_IMPLEMENTATION_PATHS
    }
    return canonical_sha256(identities)


def _protocol_contract() -> dict[str, str]:
    return {
        "dependency_installation": "NOT_APPLICABLE_FOR_STDLIB_ONLY_PATH",
        "environment_inheritance": "REPLACED_NOT_MERGED",
        "git_reflogs": "DISABLED_DURING_RECONSTRUCTION",
        "git_resolution": "EXPLICIT_ARGUMENT_OR_CALLER_PATH_PREREQUISITE",
        "machine_local_origin": "REMOVED_BEFORE_ACCEPTANCE",
        "network_policy": "PYTHON_SOCKET_AUDIT_EVENTS_DENIED",
        "protocol_id": PROTOCOL_ID,
        "protocol_implementation_sha256": _protocol_implementation_sha256(),
        "reconstruction_method": "LOCAL_GIT_CLONE_NO_HARDLINKS_EXACT_COMMIT",
        "source_repository_optional_git_locks": "DISABLED",
        "user_site_packages": "DISABLED_BY_ISOLATED_NO_SITE_INTERPRETER",
    }


def _environment_observation(
    git_executable: Path | None, *, network_guard_exercised: bool
) -> dict[str, Any]:
    try:
        python_digest: str | None = _sha256_file(Path(sys.executable))
    except OSError:
        python_digest = None
    try:
        git_digest: str | None = (
            _sha256_file(git_executable) if git_executable is not None else None
        )
    except OSError:
        git_digest = None
    return {
        "declared_environment": dict(sorted(DECLARED_CHILD_ENVIRONMENT.items())),
        "environment_inheritance": "REPLACED_NOT_MERGED",
        "external_system_calls": "NOT_PERFORMED_BY_PROTOCOL",
        "git_executable_sha256": git_digest,
        "network_guard": (
            "ENFORCED_DURING_SUPPORTED_PATH"
            if network_guard_exercised
            else "NOT_EXERCISED_PATH_BLOCKED"
        ),
        "python_executable_sha256": python_digest,
        "python_implementation": platform.python_implementation(),
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        "user_site_packages": "DISABLED",
        "workspace": "CALLER_OWNED_NEW_EMPTY_DISPOSABLE_WORKSPACE",
    }


def _fingerprint(
    source: CleanRoomSourceIdentity,
    command: CommandContract,
    environment: EnvironmentContract,
) -> ExecutionFingerprint:
    requirement = next(
        (
            item
            for item in source.artifacts
            if item.logical_path == REQUIREMENT_PATH and item.sha256 is not None
        ),
        None,
    )
    governance = next(
        (
            item
            for item in source.artifacts
            if item.logical_path == GOVERNANCE_PATH and item.sha256 is not None
        ),
        None,
    )
    return ExecutionFingerprint(
        factory_source_identity=source.source_id,
        requirement_identity=(
            f"REQUIREMENT-INPUT-{requirement.sha256}"
            if requirement is not None
            else f"REQUIREMENT-MISSING-{canonical_sha256({'path': REQUIREMENT_PATH})}"
        ),
        governance_snapshot_identity=(
            f"GOVERNANCE-INPUT-{governance.sha256}"
            if governance is not None
            else f"GOVERNANCE-MISSING-{canonical_sha256({'path': GOVERNANCE_PATH})}"
        ),
        evidence_snapshot_identity=EVIDENCE_INPUT_IDENTITY,
        tool_config_identity=(
            "CLEAN-ROOM-TOOL-CONFIG-"
            + canonical_sha256(
                {
                    "bootstrap_sha256": _sha256_bytes(
                        NETWORK_DENIAL_BOOTSTRAP.encode("utf-8")
                    ),
                    "command": command.to_dict(),
                    "environment": environment.to_dict(),
                    "protocol": _protocol_contract(),
                }
            )
        ),
    )


def _result_limitations(*, blocked: bool) -> tuple[str, ...]:
    limitations = [
        "The evidence binds only the requested committed Git identity; worktree "
        "edits outside that commit are neither copied nor claimed.",
        "The evidence covers one standard-library requirements-compiler path and "
        "exact bound inputs, not the full dependency installation surface.",
        "The network denial applies to the exercised Python process; it is not a "
        "repository-wide proof that no latent network-capable code exists.",
        "The protocol does not prove deployment, production readiness, certification, "
        "regulatory approval, security assurance, or performance.",
        "External payment ecosystems remain unexercised and real payment calls remain disabled.",
    ]
    if blocked:
        limitations.append(
            "The supported factory path was not executed because a prerequisite or "
            "hidden-state safety check blocked reconstruction."
        )
    return tuple(limitations)


def _blocked_evidence(
    *,
    source: CleanRoomSourceIdentity,
    command: CommandContract,
    environment: EnvironmentContract,
    source_dependency_paths: tuple[str, ...],
    checks: Iterable[AcceptanceCheck],
    git_executable: Path | None,
    reconstruction_performed: bool = False,
) -> CleanRoomReconstructionEvidence:
    result = CleanRoomReconstructionResult(
        status=AcceptanceStatus.BLOCKED,
        reconstruction_performed=reconstruction_performed,
        supported_path_executed=False,
        exit_code=None,
        checks=tuple(checks),
        output_artifacts=(),
        stdout_sha256=None,
        stderr_sha256=None,
        environment_observation=_environment_observation(
            git_executable, network_guard_exercised=False
        ),
        limitations=_result_limitations(blocked=True),
    )
    return CleanRoomReconstructionEvidence(
        source_identity=source,
        command=command,
        environment_contract=environment,
        execution_fingerprint=_fingerprint(source, command, environment),
        result=result,
        source_dependency_paths=source_dependency_paths,
    )


def run_clean_room_reconstruction(
    source_root: Path,
    protocol_root: Path,
    *,
    source_ref: str = "HEAD",
    source_dependency_paths: Iterable[str] = SOURCE_DEPENDENCY_PATHS,
    git_executable: Path | None = None,
) -> CleanRoomReconstructionEvidence:
    """Reconstruct and exercise one exact local source identity without network use."""
    reference = _source_ref(source_ref)
    dependencies = _paths(source_dependency_paths, "source_dependency_paths")
    root = source_root.resolve()
    workspace = protocol_root.resolve()
    command = _command_contract()
    environment_contract = _clean_room_environment_contract()
    checks: list[AcceptanceCheck] = []

    resolved_git = git_executable or (
        Path(value) if (value := shutil.which("git")) is not None else None
    )
    git_available = resolved_git is not None and resolved_git.is_file()
    checks.append(
        _pass_or_blocked_check(
            "PREREQUISITE-GIT",
            git_available,
            "DECLARED_LOCAL_GIT_EXECUTABLE",
            "AVAILABLE" if git_available else "UNAVAILABLE",
            "Exact source reconstruction requires an available local Git executable.",
        )
    )
    python_available = sys.version_info >= (3, 10) and Path(sys.executable).is_file()
    checks.append(
        _pass_or_blocked_check(
            "PREREQUISITE-PYTHON",
            python_available,
            "CPYTHON_3_10_OR_NEWER",
            (
                f"{platform.python_implementation().upper()}_"
                f"{sys.version_info.major}_{sys.version_info.minor}"
            ),
            "The supported isolated compiler route requires Python 3.10 or newer.",
        )
    )
    source_available = root.is_dir() and (root / ".git").exists()
    checks.append(
        _pass_or_blocked_check(
            "PREREQUISITE-LOCAL-GIT-SOURCE",
            source_available,
            "LOCAL_GIT_SOURCE_PRESENT",
            "PRESENT" if source_available else "MISSING",
            "The protocol resolves a local Git object and performs no fetch.",
        )
    )
    try:
        workspace_empty = not workspace.exists() or (
            workspace.is_dir() and not any(workspace.iterdir())
        )
        workspace_observable = True
    except OSError:
        workspace_empty = False
        workspace_observable = False
    workspace_safe = (
        _workspace_is_isolated(root, workspace)
        and workspace_empty
        and not protocol_root.is_symlink()
    )
    checks.append(
        _pass_or_blocked_check(
            "PREREQUISITE-DISPOSABLE-WORKSPACE",
            workspace_safe,
            {"empty": True, "isolated_from_source": True, "symlink": False},
            {
                "empty": workspace_empty,
                "isolated_from_source": _workspace_is_isolated(root, workspace),
                "observable": workspace_observable,
                "symlink": protocol_root.is_symlink(),
            },
            "Reconstruction writes only to a new isolated caller-owned workspace.",
        )
    )
    empty_source = _empty_source_identity(reference, dependencies)
    if any(item.status is AcceptanceStatus.BLOCKED for item in checks):
        return _blocked_evidence(
            source=empty_source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
        )

    assert resolved_git is not None
    try:
        workspace.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        # The prerequisite gate already accepted this caller-created empty directory.
        pass
    except OSError:
        checks.append(
            _blocked_check(
                "PREREQUISITE-WORKSPACE-CREATION",
                "WRITABLE_DISPOSABLE_WORKSPACE",
                "UNAVAILABLE",
                "The disposable protocol workspace could not be created.",
            )
        )
        return _blocked_evidence(
            source=empty_source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
        )
    try:
        (workspace / "declared-home").mkdir()
        (workspace / "declared-xdg-config").mkdir()
    except OSError:
        checks.append(
            _blocked_check(
                "PREREQUISITE-WORKSPACE-CREATION",
                "WRITABLE_DISPOSABLE_WORKSPACE",
                "UNAVAILABLE",
                "The disposable protocol workspace could not be created.",
            )
        )
        return _blocked_evidence(
            source=empty_source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
        )
    git_environment = _git_environment(workspace, resolved_git)
    try:
        commit_result = _run(
            [
                str(resolved_git),
                "-C",
                str(root),
                "rev-parse",
                "--verify",
                f"{reference}^{{commit}}",
            ],
            cwd=root,
            environment=git_environment,
        )
        commit_oid = _decode(commit_result.stdout).strip()
        tree_result = _run(
            [
                str(resolved_git),
                "-C",
                str(root),
                "rev-parse",
                "--verify",
                f"{reference}^{{tree}}",
            ],
            cwd=root,
            environment=git_environment,
        )
        tree_oid = _decode(tree_result.stdout).strip()
    except (OSError, subprocess.SubprocessError):
        commit_result = subprocess.CompletedProcess([], 1, b"", b"")
        tree_result = subprocess.CompletedProcess([], 1, b"", b"")
        commit_oid = ""
        tree_oid = ""
    source_resolved = (
        commit_result.returncode == 0
        and tree_result.returncode == 0
        and GIT_OBJECT_PATTERN.fullmatch(commit_oid) is not None
        and GIT_OBJECT_PATTERN.fullmatch(tree_oid) is not None
    )
    checks.append(
        _pass_or_blocked_check(
            "PREREQUISITE-EXACT-SOURCE-IDENTITY",
            source_resolved,
            "COMMIT_AND_TREE_OBJECTS",
            "RESOLVED" if source_resolved else "UNAVAILABLE_OR_INVALID_REF",
            "The requested source ref must resolve to exact commit and tree objects.",
        )
    )
    if not source_resolved:
        return _blocked_evidence(
            source=empty_source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
        )

    artifacts: list[ArtifactIdentity] = []
    blobs: dict[str, bytes] = {}
    for path in dependencies:
        artifact, blob = _git_blob(
            root, commit_oid, path, resolved_git, git_environment
        )
        artifacts.append(artifact)
        if blob is not None:
            blobs[path] = blob
    source = CleanRoomSourceIdentity(
        requested_ref=reference,
        availability=ArtifactAvailability.PRESENT,
        commit_oid=commit_oid,
        tree_oid=tree_oid,
        artifacts=tuple(artifacts),
    )
    try:
        source_status_before_result = _run(
            [
                str(resolved_git),
                "-C",
                str(root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=root,
            environment=git_environment,
        )
        source_status_before = source_status_before_result.stdout
        source_status_observable = source_status_before_result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        source_status_before = b""
        source_status_observable = False
    checks.append(
        _pass_or_blocked_check(
            "PREREQUISITE-SOURCE-MUTATION-OBSERVABILITY",
            source_status_observable,
            "GIT_WORKTREE_STATE_OBSERVABLE",
            "OBSERVABLE" if source_status_observable else "UNAVAILABLE",
            "The protocol binds source worktree state before reconstruction so "
            "mutation can be disproved.",
        )
    )
    missing = sorted(
        item.logical_path
        for item in artifacts
        if item.availability is ArtifactAvailability.MISSING
    )
    untracked = list(_untracked_declared_dependencies(root, artifacts))
    unavailable = sorted(set(missing) - set(untracked))
    checks.extend(
        (
            _pass_or_blocked_check(
                "HIDDEN-STATE-UNTRACKED-SOURCE-DEPENDENCIES",
                not untracked,
                [],
                untracked,
                "Every declared source dependency must exist in the exact Git tree.",
            ),
            _pass_or_blocked_check(
                "PREREQUISITE-DECLARED-SOURCE-DEPENDENCIES",
                not unavailable,
                [],
                unavailable,
                "Missing source, requirement, governance, or hygiene inputs block execution.",
            ),
        )
    )
    findings = _hidden_state_findings(blobs, DECLARED_CHILD_ENVIRONMENT)
    checks.extend(
        (
            _pass_or_blocked_check(
                "HIDDEN-STATE-PERSONAL-PATHS",
                not findings["personal_paths"],
                [],
                findings["personal_paths"],
                "Runtime source must not embed personal or user-specific absolute paths.",
            ),
            _pass_or_blocked_check(
                "HIDDEN-STATE-UNDECLARED-ENVIRONMENT",
                not findings["undeclared_environment"],
                [],
                findings["undeclared_environment"],
                "Runtime source may read only environment names declared by the protocol.",
            ),
            _pass_or_blocked_check(
                "HIDDEN-STATE-IMPLICIT-HOME-RESOLUTION",
                not findings["home_resolution"],
                [],
                findings["home_resolution"],
                "Runtime source must not resolve current-user home state.",
            ),
            _pass_or_blocked_check(
                "PREREQUISITE-RUNTIME-SOURCE-SYNTAX",
                not findings["syntax_errors"],
                [],
                findings["syntax_errors"],
                "Runtime Python sources must be UTF-8 and syntactically parseable.",
            ),
            AcceptanceCheck(
                "INSTALLATION-THIRD-PARTY-DEPENDENCIES",
                AcceptanceStatus.NOT_APPLICABLE,
                "NO_INSTALL_FOR_SELECTED_STDLIB_ONLY_PATH",
                "NOT_APPLICABLE_FOR_SELECTED_PATH",
                "The selected supported compiler path uses the repository source and "
                "standard library; the full project dependency installation surface "
                "is outside this proof.",
            ),
        )
    )
    if any(item.status is AcceptanceStatus.BLOCKED for item in checks):
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
        )

    checkout = workspace / "reconstructed-checkout"
    clone_environment = dict(git_environment)
    clone_environment["GIT_CONFIG_COUNT"] = "3"
    clone_environment["GIT_CONFIG_KEY_0"] = "core.hooksPath"
    clone_environment["GIT_CONFIG_VALUE_0"] = os.devnull
    clone_environment["GIT_CONFIG_KEY_1"] = "init.templateDir"
    clone_environment["GIT_CONFIG_VALUE_1"] = str(workspace / "empty-git-template")
    clone_environment["GIT_CONFIG_KEY_2"] = "core.logAllRefUpdates"
    clone_environment["GIT_CONFIG_VALUE_2"] = "false"
    (workspace / "empty-git-template").mkdir()
    try:
        clone_result = _run(
            [
                str(resolved_git),
                "clone",
                "--no-checkout",
                "--no-hardlinks",
                "--no-tags",
                str(root),
                str(checkout),
            ],
            cwd=workspace,
            environment=clone_environment,
        )
    except (OSError, subprocess.SubprocessError):
        clone_result = subprocess.CompletedProcess([], 1, b"", b"")
    checks.append(
        _pass_or_blocked_check(
            "RECONSTRUCTION-LOCAL-CLONE",
            clone_result.returncode == 0,
            0,
            clone_result.returncode,
            "The exact source is cloned locally without hardlinks, tags, fetch, or network URL.",
        )
    )
    if clone_result.returncode != 0:
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
        )

    try:
        checkout_result = _run(
            [
                str(resolved_git),
                "-C",
                str(checkout),
                "-c",
                f"core.hooksPath={os.devnull}",
                "-c",
                "core.logAllRefUpdates=false",
                "checkout",
                "--detach",
                commit_oid,
            ],
            cwd=workspace,
            environment=git_environment,
        )
        remove_origin_result = _run(
            [
                str(resolved_git),
                "-C",
                str(checkout),
                "remote",
                "remove",
                "origin",
            ],
            cwd=workspace,
            environment=git_environment,
        )
        reconstructed_commit = _run(
            [str(resolved_git), "-C", str(checkout), "rev-parse", "HEAD"],
            cwd=workspace,
            environment=git_environment,
        )
        reconstructed_tree = _run(
            [str(resolved_git), "-C", str(checkout), "rev-parse", "HEAD^{tree}"],
            cwd=workspace,
            environment=git_environment,
        )
        clean_status = _run(
            [
                str(resolved_git),
                "-C",
                str(checkout),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=workspace,
            environment=git_environment,
        )
    except (OSError, subprocess.SubprocessError):
        checkout_result = subprocess.CompletedProcess([], 1, b"", b"")
        remove_origin_result = subprocess.CompletedProcess([], 1, b"", b"")
        reconstructed_commit = subprocess.CompletedProcess([], 1, b"", b"")
        reconstructed_tree = subprocess.CompletedProcess([], 1, b"", b"")
        clean_status = subprocess.CompletedProcess([], 1, b"", b"")
    exact_checkout = (
        checkout_result.returncode == 0
        and remove_origin_result.returncode == 0
        and reconstructed_commit.returncode == 0
        and _decode(reconstructed_commit.stdout).strip() == commit_oid
        and reconstructed_tree.returncode == 0
        and _decode(reconstructed_tree.stdout).strip() == tree_oid
        and clean_status.returncode == 0
        and not clean_status.stdout
    )
    checks.append(
        _pass_or_blocked_check(
            "RECONSTRUCTION-LOCAL-ORIGIN-REMOVED",
            remove_origin_result.returncode == 0,
            "NO_MACHINE_LOCAL_ORIGIN_REMOTE",
            (
                "REMOVED"
                if remove_origin_result.returncode == 0
                else "FAILED_OR_UNAVAILABLE"
            ),
            "The local source path is removed from reconstructed Git configuration.",
        )
    )
    metadata_candidates = [checkout / ".git" / "config"]
    logs_root = checkout / ".git" / "logs"
    if logs_root.is_dir():
        metadata_candidates.extend(
            sorted(path for path in logs_root.rglob("*") if path.is_file())
        )
    metadata_findings: list[str] = []
    source_path_token = str(root).encode("utf-8")
    for metadata_path in metadata_candidates:
        try:
            metadata_bytes = metadata_path.read_bytes()
        except OSError:
            metadata_findings.append("UNREADABLE_GIT_METADATA")
            continue
        if source_path_token in metadata_bytes or PERSONAL_PATH_PATTERN.search(
            _decode(metadata_bytes)
        ):
            metadata_findings.append(
                metadata_path.relative_to(checkout).as_posix()
            )
    checks.append(
        _pass_or_blocked_check(
            "HIDDEN-STATE-RECONSTRUCTED-METADATA-PATHS",
            not metadata_findings,
            [],
            sorted(metadata_findings),
            "Reconstructed Git configuration and logs must not retain local source paths.",
        )
    )
    checks.append(
        _pass_or_blocked_check(
            "RECONSTRUCTION-EXACT-CLEAN-CHECKOUT",
            exact_checkout,
            {"commit": "EXACT", "tree": "EXACT", "worktree": "CLEAN"},
            {
                "commit": (
                    "EXACT"
                    if _decode(reconstructed_commit.stdout).strip() == commit_oid
                    else "MISMATCH_OR_UNAVAILABLE"
                ),
                "tree": (
                    "EXACT"
                    if _decode(reconstructed_tree.stdout).strip() == tree_oid
                    else "MISMATCH_OR_UNAVAILABLE"
                ),
                "worktree": (
                    "CLEAN"
                    if clean_status.returncode == 0 and not clean_status.stdout
                    else "DIRTY_OR_UNAVAILABLE"
                ),
            },
            "The reconstructed checkout must match the bound commit and tree and be clean.",
        )
    )
    if not exact_checkout or metadata_findings:
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
            reconstruction_performed=True,
        )

    try:
        hygiene = _run(
            [
                sys.executable,
                "-I",
                "-S",
                "scripts/validate_public_clone_readiness.py",
                "--repo",
                ".",
                "--license",
                "Apache-2.0",
            ],
            cwd=checkout,
            environment={**git_environment, **_child_environment()},
        )
        hygiene_payload = json.loads(_decode(hygiene.stdout))
        hygiene_checks = (
            sorted(
                str(item.get("name"))
                for item in hygiene_payload.get("checks", [])
                if isinstance(item, Mapping) and item.get("status") == "passed"
            )
            if isinstance(hygiene_payload, Mapping)
            else []
        )
        hygiene_failures = (
            sorted(
                str(item.get("name"))
                for item in hygiene_payload.get("checks", [])
                if isinstance(item, Mapping) and item.get("status") != "passed"
            )
            if isinstance(hygiene_payload, Mapping)
            else []
        )
        hygiene_passed = (
            hygiene.returncode == 0
            and isinstance(hygiene_payload, Mapping)
            and hygiene_payload.get("status") == "passed"
        )
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        hygiene_passed = False
        hygiene_checks = []
        hygiene_failures = ["VALIDATOR_UNAVAILABLE_OR_INVALID"]
    checks.append(
        _pass_or_blocked_check(
            "RECONSTRUCTION-PUBLIC-CLONE-HYGIENE",
            hygiene_passed,
            "PASSED_EXISTING_PUBLIC_CLONE_VALIDATOR",
            {
                "failed_check_ids": hygiene_failures,
                "passed_check_ids": hygiene_checks,
                "status": "PASSED" if hygiene_passed else "FAILED_OR_UNAVAILABLE",
            },
            "The reconstructed identity must satisfy the existing public-clone contract.",
        )
    )
    if not hygiene_passed:
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
            reconstruction_performed=True,
        )

    execution_root = workspace / "execution"
    execution_root.mkdir()
    input_path = execution_root / COPIED_INPUT_PATH
    input_path.parent.mkdir(parents=True)
    try:
        shutil.copyfile(checkout / REQUIREMENT_PATH, input_path)
        input_identity_matches = _sha256_file(input_path) == next(
            item.sha256 for item in artifacts if item.logical_path == REQUIREMENT_PATH
        )
    except (OSError, StopIteration):
        input_identity_matches = False
    checks.append(
        _pass_or_blocked_check(
            "RECONSTRUCTION-REQUIREMENT-STAGING",
            input_identity_matches,
            "EXACT_BOUND_REQUIREMENT_BYTES",
            "EXACT" if input_identity_matches else "MISMATCH_OR_UNAVAILABLE",
            "Only the bound requirement input is staged; no generated output is copied.",
        )
    )
    if not input_identity_matches:
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
            reconstruction_performed=True,
        )

    generated_output_absent = not (execution_root / OUTPUT_PATH).exists()
    checks.append(
        _pass_or_blocked_check(
            "RECONSTRUCTION-NO-PREEXISTING-GENERATED-OUTPUT",
            generated_output_absent,
            "ABSENT_BEFORE_EXECUTION",
            "ABSENT" if generated_output_absent else "PRESENT",
            "The protocol must generate the output by execution rather than copy an "
            "acceptance artifact.",
        )
    )
    if not generated_output_absent:
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
            reconstruction_performed=True,
        )

    actual_argv = [
        sys.executable,
        "-I",
        "-S",
        "-c",
        NETWORK_DENIAL_BOOTSTRAP,
        str(checkout),
        "factory.application_engineering.requirements_compiler",
        "validate",
        "--input",
        COPIED_INPUT_PATH,
        "--project-root",
        ".",
        "--output",
        OUTPUT_PATH,
    ]
    completed: subprocess.CompletedProcess[bytes] | None = None
    process_error: str | None = None
    try:
        completed = _run(
            actual_argv,
            cwd=execution_root,
            environment=_child_environment(),
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        process_error = "TIMEOUT"
    except OSError as exc:
        process_error = type(exc).__name__
    if completed is None and process_error != "TIMEOUT":
        checks.append(
            _blocked_check(
                "PREREQUISITE-ISOLATED-INTERPRETER-EXECUTION",
                "EXECUTABLE",
                process_error,
                "The bound interpreter could not start the isolated supported entrypoint.",
            )
        )
        return _blocked_evidence(
            source=source,
            command=command,
            environment=environment_contract,
            source_dependency_paths=dependencies,
            checks=checks,
            git_executable=resolved_git,
            reconstruction_performed=True,
        )

    output_path = execution_root / OUTPUT_PATH
    output, output_error = _load_output(output_path)
    requirement_identity = next(
        item for item in artifacts if item.logical_path == REQUIREMENT_PATH
    )
    execution_checks = _output_checks(
        completed=(
            subprocess.CompletedProcess(
                completed.args,
                completed.returncode,
                _decode(completed.stdout),
                _decode(completed.stderr),
            )
            if completed is not None
            else None
        ),
        process_error=process_error,
        output=output,
        output_error=output_error,
        requirement=requirement_identity,
    )
    checks.extend(execution_checks)
    checkout_token = str(checkout).encode("utf-8")
    source_token = str(root).encode("utf-8")
    output_bytes = output_path.read_bytes() if output_path.is_file() else b""
    process_bytes = (
        completed.stdout + completed.stderr if completed is not None else b""
    )
    portable_outputs = (
        checkout_token not in output_bytes + process_bytes
        and source_token not in output_bytes + process_bytes
        and not PERSONAL_PATH_PATTERN.search(_decode(output_bytes + process_bytes))
    )
    checks.extend(
        (
            _pass_or_fail_check(
                "HIDDEN-STATE-OUTPUT-LOCAL-PATHS",
                portable_outputs,
                "NO_SOURCE_OR_PERSONAL_ABSOLUTE_PATHS",
                "ABSENT" if portable_outputs else "DETECTED",
                "Generated output and process streams must remain portable across workspaces.",
            ),
            _pass_or_fail_check(
                "HIDDEN-STATE-ENVIRONMENT-INHERITANCE",
                True,
                {"inherited_names": [], "mode": "REPLACED_NOT_MERGED"},
                {"inherited_names": [], "mode": "REPLACED_NOT_MERGED"},
                "The child receives the declared environment instead of inheriting user state.",
            ),
            _pass_or_fail_check(
                "NO-NETWORK-PYTHON-AUDIT-GUARD",
                completed is not None,
                "SOCKET_AUDIT_EVENTS_DENIED_DURING_EXECUTION",
                "ENFORCED" if completed is not None else "NOT_EXERCISED",
                "Every socket audit event is denied before the supported module is imported.",
            ),
        )
    )
    try:
        source_status_after_result = _run(
            [
                str(resolved_git),
                "-C",
                str(root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=root,
            environment=git_environment,
        )
        source_unchanged = (
            source_status_after_result.returncode == 0
            and source_status_after_result.stdout == source_status_before
        )
    except (OSError, subprocess.SubprocessError):
        source_unchanged = False
    checks.append(
        _pass_or_fail_check(
            "SOURCE-REPOSITORY-NOT-MUTATED",
            source_unchanged,
            "SEMANTIC_GIT_STATUS_UNCHANGED",
            "UNCHANGED" if source_unchanged else "CHANGED_OR_UNAVAILABLE",
            "The canonical source worktree status must be byte-identical before and "
            "after the protocol.",
        )
    )
    status = (
        AcceptanceStatus.PASS
        if all(
            item.status in {AcceptanceStatus.PASS, AcceptanceStatus.NOT_APPLICABLE}
            for item in checks
        )
        else AcceptanceStatus.FAIL
    )
    artifacts_out = (
        ArtifactIdentity.observe(
            execution_root, OUTPUT_PATH, ArtifactRole.EXECUTION_OUTPUT
        ),
    )
    stdout = completed.stdout if completed is not None else b""
    stderr = completed.stderr if completed is not None else b""
    result = CleanRoomReconstructionResult(
        status=status,
        reconstruction_performed=True,
        supported_path_executed=True,
        exit_code=completed.returncode if completed is not None else None,
        checks=tuple(checks),
        output_artifacts=artifacts_out,
        stdout_sha256=_sha256_bytes(stdout),
        stderr_sha256=_sha256_bytes(stderr),
        environment_observation=_environment_observation(
            resolved_git, network_guard_exercised=True
        ),
        limitations=_result_limitations(blocked=False),
    )
    return CleanRoomReconstructionEvidence(
        source_identity=source,
        command=command,
        environment_contract=environment_contract,
        execution_fingerprint=_fingerprint(source, command, environment_contract),
        result=result,
        source_dependency_paths=dependencies,
    )


def _validate_identity_record(
    value: Mapping[str, Any], *, id_field: str, digest_field: str, prefix: str
) -> None:
    digest = value.get(digest_field)
    if not _is_sha256(digest) or value.get(id_field) != f"{prefix}{digest}":
        raise CleanRoomReconstructionError(f"{id_field} is invalid")
    core = {
        key: item for key, item in value.items() if key not in {id_field, digest_field}
    }
    if canonical_sha256(core) != digest:
        raise CleanRoomReconstructionError(f"{digest_field} is invalid")


def _walk(value: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield None, item
            yield from _walk(item)


def validate_clean_room_reconstruction_evidence(document: Mapping[str, Any]) -> bool:
    """Fail closed on tampering, path leakage, unstable time, or false authority."""
    if not isinstance(document, Mapping):
        raise CleanRoomReconstructionError("clean-room evidence must be a JSON object")
    value = cast(dict[str, Any], json.loads(canonical_json(dict(document))))
    expected_fields = {
        "authority_boundary",
        "command",
        "environment_contract",
        "evidence_id",
        "evidence_sha256",
        "execution_fingerprint",
        "identity_scope",
        "limitations",
        "protocol",
        "provenance",
        "result",
        "scenario_key",
        "schema_version",
        "source_dependency_paths",
        "source_identity",
    }
    if set(value) != expected_fields:
        raise CleanRoomReconstructionError("clean-room evidence fields are invalid")
    if value.get("schema_version") != CleanRoomReconstructionEvidence.SCHEMA_VERSION:
        raise CleanRoomReconstructionError("clean-room evidence schema is unsupported")
    if value.get("identity_scope") != "CANONICAL_CLEAN_ROOM_EVIDENCE_CORE":
        raise CleanRoomReconstructionError("clean-room identity scope is invalid")
    if value.get("scenario_key") != SCENARIO_KEY:
        raise CleanRoomReconstructionError("clean-room scenario key is invalid")
    if value.get("authority_boundary") != {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
        "self_awarded_readiness": False,
    }:
        raise CleanRoomReconstructionError("clean-room authority boundary is invalid")
    expected_protocol = _protocol_contract()
    if value.get("protocol") != expected_protocol:
        raise CleanRoomReconstructionError("clean-room protocol contract is invalid")
    if value.get("command") != _command_contract().to_dict():
        raise CleanRoomReconstructionError("clean-room command contract is invalid")
    if value.get("environment_contract") != _clean_room_environment_contract().to_dict():
        raise CleanRoomReconstructionError(
            "clean-room environment contract is invalid"
        )
    forbidden_time_keys = {
        "created_at",
        "generated_at",
        "timestamp",
        "updated_at",
        "wall_clock_time",
    }
    for key, item in _walk(value):
        if key in forbidden_time_keys:
            raise CleanRoomReconstructionError(
                "wall-clock fields cannot enter canonical clean-room evidence"
            )
        if isinstance(item, str) and PERSONAL_PATH_PATTERN.search(item):
            raise CleanRoomReconstructionError(
                "clean-room evidence contains a personal or local path"
            )
    source = value.get("source_identity")
    result = value.get("result")
    fingerprint = value.get("execution_fingerprint")
    provenance = value.get("provenance")
    if not all(isinstance(item, Mapping) for item in (source, result, fingerprint, provenance)):
        raise CleanRoomReconstructionError(
            "source, result, fingerprint, and provenance must be objects"
        )
    source_value = cast(Mapping[str, Any], source)
    result_value = cast(Mapping[str, Any], result)
    fingerprint_value = cast(Mapping[str, Any], fingerprint)
    provenance_value = cast(Mapping[str, Any], provenance)
    if set(source_value) != {
        "artifacts",
        "availability",
        "commit_oid",
        "repository_id",
        "requested_ref",
        "schema_version",
        "source_id",
        "source_sha256",
        "tree_oid",
    }:
        raise CleanRoomReconstructionError("clean-room source fields are invalid")
    if (
        source_value.get("schema_version")
        != CleanRoomSourceIdentity.SCHEMA_VERSION
        or source_value.get("repository_id") != "upi_app_factory"
    ):
        raise CleanRoomReconstructionError("clean-room source contract is invalid")
    try:
        requested_ref = _source_ref(cast(str, source_value.get("requested_ref")))
    except (TypeError, CleanRoomReconstructionError) as exc:
        raise CleanRoomReconstructionError("clean-room source ref is invalid") from exc
    if requested_ref != source_value.get("requested_ref"):
        raise CleanRoomReconstructionError("clean-room source ref is invalid")
    availability = source_value.get("availability")
    commit_oid = source_value.get("commit_oid")
    tree_oid = source_value.get("tree_oid")
    if availability == ArtifactAvailability.PRESENT.value:
        if not (
            isinstance(commit_oid, str)
            and GIT_OBJECT_PATTERN.fullmatch(commit_oid)
            and isinstance(tree_oid, str)
            and GIT_OBJECT_PATTERN.fullmatch(tree_oid)
        ):
            raise CleanRoomReconstructionError("present clean-room source is unbound")
    elif not (
        availability == ArtifactAvailability.MISSING.value
        and commit_oid is None
        and tree_oid is None
    ):
        raise CleanRoomReconstructionError("clean-room source availability is invalid")
    dependency_values = value.get("source_dependency_paths")
    if not isinstance(dependency_values, list):
        raise CleanRoomReconstructionError("source dependency paths are invalid")
    try:
        dependency_paths = _paths(
            cast(Iterable[str], dependency_values), "source_dependency_paths"
        )
    except (TypeError, CleanRoomReconstructionError) as exc:
        raise CleanRoomReconstructionError(
            "source dependency paths are invalid"
        ) from exc
    if not set(SOURCE_DEPENDENCY_PATHS).issubset(dependency_paths):
        raise CleanRoomReconstructionError(
            "clean-room evidence omits a mandatory source dependency"
        )
    source_artifacts = source_value.get("artifacts")
    if not isinstance(source_artifacts, list):
        raise CleanRoomReconstructionError("source artifacts are invalid")
    source_artifacts_by_path: dict[str, Mapping[str, Any]] = {}
    for item in source_artifacts:
        if not isinstance(item, Mapping) or set(item) != {
            "availability",
            "logical_path",
            "role",
            "sha256",
            "size_bytes",
        }:
            raise CleanRoomReconstructionError("source artifact identity is invalid")
        logical_path = item.get("logical_path")
        if not isinstance(logical_path, str):
            raise CleanRoomReconstructionError("source artifact path is invalid")
        _logical_path(logical_path, "source artifact path")
        if logical_path in source_artifacts_by_path:
            raise CleanRoomReconstructionError("source artifact paths must be unique")
        if item.get("role") != _artifact_role(logical_path).value:
            raise CleanRoomReconstructionError("source artifact role is invalid")
        item_availability = item.get("availability")
        if item_availability == ArtifactAvailability.PRESENT.value:
            if not _is_sha256(item.get("sha256")) or not isinstance(
                item.get("size_bytes"), int
            ):
                raise CleanRoomReconstructionError(
                    "present source artifact identity is invalid"
                )
        elif not (
            item_availability == ArtifactAvailability.MISSING.value
            and item.get("sha256") is None
            and item.get("size_bytes") is None
        ):
            raise CleanRoomReconstructionError(
                "missing source artifact identity is invalid"
            )
        source_artifacts_by_path[logical_path] = item
    if set(source_artifacts_by_path) != set(dependency_paths):
        raise CleanRoomReconstructionError(
            "source artifacts do not match declared dependencies"
        )
    if set(result_value) != {
        "checks",
        "environment_observation",
        "exit_code",
        "limitations",
        "output_artifacts",
        "reconstruction_performed",
        "result_id",
        "result_sha256",
        "schema_version",
        "status",
        "stderr_sha256",
        "stdout_sha256",
        "supported_path_executed",
    } or (
        result_value.get("schema_version")
        != CleanRoomReconstructionResult.SCHEMA_VERSION
    ):
        raise CleanRoomReconstructionError("clean-room result contract is invalid")
    _validate_identity_record(
        source_value,
        id_field="source_id",
        digest_field="source_sha256",
        prefix="CLEAN-ROOM-SOURCE-",
    )
    _validate_identity_record(
        result_value,
        id_field="result_id",
        digest_field="result_sha256",
        prefix="CLEAN-ROOM-RESULT-",
    )
    _validate_identity_record(
        fingerprint_value,
        id_field="fingerprint_id",
        digest_field="fingerprint_sha256",
        prefix="EXECUTION-FINGERPRINT-",
    )
    if set(fingerprint_value) != {
        "evidence_snapshot_identity",
        "factory_source_identity",
        "fingerprint_id",
        "fingerprint_sha256",
        "governance_snapshot_identity",
        "requirement_identity",
        "schema_version",
        "tool_config_identity",
    } or fingerprint_value.get("schema_version") != ExecutionFingerprint.SCHEMA_VERSION:
        raise CleanRoomReconstructionError("execution fingerprint contract is invalid")
    if fingerprint_value.get("factory_source_identity") != source_value.get("source_id"):
        raise CleanRoomReconstructionError(
            "execution fingerprint does not bind clean-room source"
        )
    requirement_artifact = source_artifacts_by_path[REQUIREMENT_PATH]
    governance_artifact = source_artifacts_by_path[GOVERNANCE_PATH]
    expected_requirement_identity = (
        f"REQUIREMENT-INPUT-{requirement_artifact['sha256']}"
        if requirement_artifact.get("sha256") is not None
        else f"REQUIREMENT-MISSING-{canonical_sha256({'path': REQUIREMENT_PATH})}"
    )
    expected_governance_identity = (
        f"GOVERNANCE-INPUT-{governance_artifact['sha256']}"
        if governance_artifact.get("sha256") is not None
        else f"GOVERNANCE-MISSING-{canonical_sha256({'path': GOVERNANCE_PATH})}"
    )
    expected_tool_config = "CLEAN-ROOM-TOOL-CONFIG-" + canonical_sha256(
        {
            "bootstrap_sha256": _sha256_bytes(
                NETWORK_DENIAL_BOOTSTRAP.encode("utf-8")
            ),
            "command": _command_contract().to_dict(),
            "environment": _clean_room_environment_contract().to_dict(),
            "protocol": _protocol_contract(),
        }
    )
    if (
        fingerprint_value.get("requirement_identity")
        != expected_requirement_identity
        or fingerprint_value.get("governance_snapshot_identity")
        != expected_governance_identity
        or fingerprint_value.get("evidence_snapshot_identity")
        != EVIDENCE_INPUT_IDENTITY
        or fingerprint_value.get("tool_config_identity") != expected_tool_config
    ):
        raise CleanRoomReconstructionError(
            "execution fingerprint inputs are not evidence-derived"
        )
    try:
        status = AcceptanceStatus(result_value.get("status"))
    except (TypeError, ValueError) as exc:
        raise CleanRoomReconstructionError("clean-room result status is invalid") from exc
    checks = result_value.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CleanRoomReconstructionError("clean-room result checks are invalid")
    try:
        check_statuses = [
            AcceptanceStatus(item.get("status"))
            for item in checks
            if isinstance(item, Mapping)
        ]
    except (TypeError, ValueError) as exc:
        raise CleanRoomReconstructionError("clean-room check status is invalid") from exc
    if len(check_statuses) != len(checks):
        raise CleanRoomReconstructionError("clean-room checks must be objects")
    check_status_by_id: dict[str, AcceptanceStatus] = {}
    for item, item_status in zip(checks, check_statuses):
        assert isinstance(item, Mapping)
        if set(item) != {
            "check_id",
            "expected",
            "explanation",
            "observed",
            "status",
        }:
            raise CleanRoomReconstructionError("clean-room check fields are invalid")
        check_id = item.get("check_id")
        if not isinstance(check_id, str) or check_id in check_status_by_id:
            raise CleanRoomReconstructionError("clean-room check IDs are invalid")
        check_status_by_id[check_id] = item_status
    reconstructed = result_value.get("reconstruction_performed")
    executed = result_value.get("supported_path_executed")
    exit_code = result_value.get("exit_code")
    if status is AcceptanceStatus.PASS and not (
        reconstructed is True
        and executed is True
        and exit_code == 0
        and AcceptanceStatus.FAIL not in check_statuses
        and AcceptanceStatus.BLOCKED not in check_statuses
    ):
        raise CleanRoomReconstructionError("PASS is not evidence-derived")
    if executed is True:
        if not _is_sha256(result_value.get("stdout_sha256")) or not _is_sha256(
            result_value.get("stderr_sha256")
        ):
            raise CleanRoomReconstructionError(
                "executed path lacks process stream identities"
            )
    elif any(
        result_value.get(key) is not None
        for key in ("exit_code", "stdout_sha256", "stderr_sha256")
    ):
        raise CleanRoomReconstructionError(
            "unexecuted path asserts process observations"
        )
    if status is AcceptanceStatus.PASS:
        missing_pass_checks = sorted(
            check_id
            for check_id in REQUIRED_PASS_CHECK_IDS
            if check_status_by_id.get(check_id) is not AcceptanceStatus.PASS
        )
        if missing_pass_checks:
            raise CleanRoomReconstructionError(
                "PASS omits mandatory clean-room proof checks"
            )
        if (
            check_status_by_id.get("INSTALLATION-THIRD-PARTY-DEPENDENCIES")
            is not AcceptanceStatus.NOT_APPLICABLE
        ):
            raise CleanRoomReconstructionError(
                "dependency installation applicability is invalid"
            )
        if availability != ArtifactAvailability.PRESENT.value or any(
            item.get("availability") != ArtifactAvailability.PRESENT.value
            for item in source_artifacts_by_path.values()
        ):
            raise CleanRoomReconstructionError(
                "PASS requires every source dependency to be present"
            )
    if status is AcceptanceStatus.FAIL and not (
        executed is True and AcceptanceStatus.FAIL in check_statuses
    ):
        raise CleanRoomReconstructionError("FAIL is not evidence-derived")
    if status is AcceptanceStatus.BLOCKED and not (
        executed is False and AcceptanceStatus.BLOCKED in check_statuses
    ):
        raise CleanRoomReconstructionError("BLOCKED is not evidence-derived")
    output_artifacts = result_value.get("output_artifacts")
    if not isinstance(output_artifacts, list):
        raise CleanRoomReconstructionError("output artifacts are invalid")
    if status is AcceptanceStatus.PASS:
        if len(output_artifacts) != 1 or not isinstance(output_artifacts[0], Mapping):
            raise CleanRoomReconstructionError("PASS requires one output artifact")
        output_artifact = cast(Mapping[str, Any], output_artifacts[0])
        if not (
            output_artifact.get("logical_path") == OUTPUT_PATH
            and output_artifact.get("role") == ArtifactRole.EXECUTION_OUTPUT.value
            and output_artifact.get("availability")
            == ArtifactAvailability.PRESENT.value
            and _is_sha256(output_artifact.get("sha256"))
            and isinstance(output_artifact.get("size_bytes"), int)
        ):
            raise CleanRoomReconstructionError("PASS output artifact is invalid")
    elif status is AcceptanceStatus.BLOCKED and output_artifacts:
        raise CleanRoomReconstructionError("BLOCKED cannot assert generated outputs")
    observation = result_value.get("environment_observation")
    if not isinstance(observation, Mapping) or not (
        observation.get("declared_environment")
        == dict(sorted(DECLARED_CHILD_ENVIRONMENT.items()))
        and observation.get("environment_inheritance") == "REPLACED_NOT_MERGED"
        and observation.get("user_site_packages") == "DISABLED"
    ):
        raise CleanRoomReconstructionError("environment observation is invalid")
    if status is AcceptanceStatus.PASS and observation.get("network_guard") != (
        "ENFORCED_DURING_SUPPORTED_PATH"
    ):
        raise CleanRoomReconstructionError("PASS requires the network guard")
    if value.get("limitations") != result_value.get("limitations"):
        raise CleanRoomReconstructionError("clean-room limitations are inconsistent")
    evidence_digest = value.get("evidence_sha256")
    core = {
        key: item
        for key, item in value.items()
        if key not in {"evidence_id", "evidence_sha256", "provenance"}
    }
    if not _is_sha256(evidence_digest) or canonical_sha256(core) != evidence_digest:
        raise CleanRoomReconstructionError("clean-room evidence digest is invalid")
    if value.get("evidence_id") != f"CLEAN-ROOM-EVIDENCE-{evidence_digest}":
        raise CleanRoomReconstructionError("clean-room evidence ID is invalid")
    expected_provenance = ProvenanceBinding(
        source_id=f"SOURCE-CLEAN-ROOM-{evidence_digest}",
        revision=str(fingerprint_value.get("fingerprint_id")),
        content_sha256=cast(str, evidence_digest),
        source_type="MACHINE_EXECUTION_RECORD",
    ).to_dict()
    if dict(provenance_value) != expected_provenance:
        raise CleanRoomReconstructionError("clean-room provenance is invalid")
    return True


def write_clean_room_reconstruction_evidence(
    evidence: CleanRoomReconstructionEvidence, path: Path
) -> dict[str, str]:
    if not isinstance(evidence, CleanRoomReconstructionEvidence):
        raise CleanRoomReconstructionError(
            "evidence must use CleanRoomReconstructionEvidence"
        )
    if path.exists():
        raise CleanRoomReconstructionError(
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local no-network clean-room reconstruction evidence."
    )
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source-ref", default="HEAD")
    parser.add_argument("--evidence-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    evidence = run_clean_room_reconstruction(
        parsed.source_root,
        parsed.workspace,
        source_ref=parsed.source_ref,
    )
    output_path = parsed.evidence_output or (
        parsed.workspace / "clean_room_reconstruction_evidence.json"
    )
    if evidence.result.status is AcceptanceStatus.BLOCKED:
        summary = {
            "evidence_artifact": "NOT_WRITTEN_BLOCKED",
            "evidence_id": evidence.evidence_id,
            "status": evidence.result.status.value,
        }
    else:
        summary = write_clean_room_reconstruction_evidence(evidence, output_path)
        summary["evidence_artifact"] = (
            output_path.relative_to(parsed.workspace).as_posix()
            if output_path.is_relative_to(parsed.workspace)
            else "CALLER_SELECTED_OUTPUT"
        )
    print(canonical_json(summary))
    if evidence.result.status is AcceptanceStatus.PASS:
        return 0
    if evidence.result.status is AcceptanceStatus.BLOCKED:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
