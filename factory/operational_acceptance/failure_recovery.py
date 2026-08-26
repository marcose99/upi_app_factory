"""Typed failure injection, governed recovery, and deterministic replay evidence.

The workflow deliberately injects one recoverable fault into the representative
operational-acceptance output: the generated artifact is moved to a quarantine
path in the caller-owned disposable workspace.  Detection compares the live
artifact to the already authenticated acceptance observation.  Recovery then
uses a second disposable workspace and the exact M2.5 execution fingerprint;
it never edits requirements, governance snapshots, gates, or the failed record.

Every status in this module is derived from structured identity comparisons.
Narrative explanations improve reviewability but are never the sole authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Iterable, Mapping, cast

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
    AcceptanceStatus,
    ArtifactAvailability,
    ArtifactIdentity,
    ArtifactRole,
    OperationalAcceptanceError,
    OperationalAcceptanceEvidence,
    _is_sha256,
    _logical_path,
    _sha256_bytes,
    _stable_identifier,
    _stable_text,
    _validate_identity_record as _validate_acceptance_identity_record,
    _walk_keys,
    run_representative_operational_acceptance,
    validate_operational_acceptance_evidence,
)


class FailureRecoveryReplayError(OperationalAcceptanceError):
    """Raised when failure or replay evidence is ambiguous or inconsistent."""


class FaultClass(str, Enum):
    """Closed set of supported deterministic fault injections."""

    EXECUTION_OUTPUT_UNAVAILABLE = "EXECUTION_OUTPUT_UNAVAILABLE"


class FaultMechanism(str, Enum):
    """Exact local operation used to inject a fault."""

    QUARANTINE_DECLARED_OUTPUT = "QUARANTINE_DECLARED_OUTPUT"


class FailureClass(str, Enum):
    """Operational diagnosis classes; these do not authorize a repair."""

    EVIDENCE_INTEGRITY_FAILURE = "EVIDENCE_INTEGRITY_FAILURE"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    PREREQUISITE_FAILURE = "PREREQUISITE_FAILURE"
    UNKNOWN = "UNKNOWN"


class ProofVerdict(str, Enum):
    """Evidence-derived verdict vocabulary used by diagnosis and replay."""

    PROVEN = "PROVEN"
    DISPROVEN = "DISPROVEN"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_MEASURED = "NOT_MEASURED"


class RecoveryAction(str, Enum):
    """Fail-closed action selected from identity evidence."""

    REPLAY_EXACT_BOUND_INPUTS = "REPLAY_EXACT_BOUND_INPUTS"
    STOP_MISSING_IDENTITY = "STOP_MISSING_IDENTITY"


REPLAY_IDENTITY_FIELDS = (
    "evidence_snapshot_identity",
    "factory_source_identity",
    "governance_snapshot_identity",
    "requirement_identity",
    "tool_config_identity",
)
QUARANTINE_PREFIX = "faults/quarantine"


def _validate_identity_record(
    value: Mapping[str, Any], *, id_field: str, digest_field: str, prefix: str
) -> None:
    """Reuse the acceptance identity primitive with this module's typed error."""
    try:
        _validate_acceptance_identity_record(
            value,
            id_field=id_field,
            digest_field=digest_field,
            prefix=prefix,
        )
    except OperationalAcceptanceError as exc:
        raise FailureRecoveryReplayError(str(exc)) from exc


def _record_collection(
    values: Iterable[Any], field_name: str, expected_type: type[Any]
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise FailureRecoveryReplayError(f"{field_name} must be a collection")
    try:
        records = tuple(values)
    except TypeError as exc:
        raise FailureRecoveryReplayError(f"{field_name} must be a collection") from exc
    if any(not isinstance(item, expected_type) for item in records):
        raise FailureRecoveryReplayError(
            f"{field_name} must contain {expected_type.__name__} values"
        )
    return records


def _normalized_limitations(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise FailureRecoveryReplayError("limitations must be a collection")
    limitations = tuple(sorted(_stable_text(item, "limitation") for item in values))
    if not limitations or len(limitations) != len(set(limitations)):
        raise FailureRecoveryReplayError("limitations must be unique and explicit")
    return limitations


def _missing_identity(value: str) -> bool:
    return "-MISSING-" in value or value.endswith("-MISSING")


@dataclass(frozen=True)
class ReplayIdentityAssessment:
    """Knowledge state for one mandatory M2.5 execution identity."""

    field_name: str
    verdict: ProofVerdict
    identity: str | None

    def __post_init__(self) -> None:
        if self.field_name not in REPLAY_IDENTITY_FIELDS:
            raise FailureRecoveryReplayError("replay identity field is unsupported")
        if not isinstance(self.verdict, ProofVerdict):
            raise FailureRecoveryReplayError("identity verdict must use ProofVerdict")
        if self.identity is not None:
            _stable_identifier(self.identity, "identity")
        if self.verdict is ProofVerdict.PROVEN:
            if self.identity is None or _missing_identity(self.identity):
                raise FailureRecoveryReplayError(
                    "PROVEN replay identities require an exact non-missing value"
                )
        elif self.verdict is ProofVerdict.UNKNOWN:
            if self.identity is not None and not _missing_identity(self.identity):
                raise FailureRecoveryReplayError(
                    "UNKNOWN replay identity must be absent or explicitly missing"
                )
        elif self.verdict is ProofVerdict.NOT_MEASURED:
            if self.identity is not None:
                raise FailureRecoveryReplayError(
                    "NOT_MEASURED replay identity cannot invent an identity value"
                )
        else:
            raise FailureRecoveryReplayError(
                "identity verdict must be PROVEN, UNKNOWN, or NOT_MEASURED"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "identity": self.identity,
            "verdict": self.verdict.value,
        }


@dataclass(frozen=True)
class ReplayIdentityBinding:
    """Exact replay inputs, including explicit unknown and unmeasured states."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.replay-identity-binding.v1"

    assessments: tuple[ReplayIdentityAssessment, ...]

    def __post_init__(self) -> None:
        assessments = _record_collection(
            self.assessments, "assessments", ReplayIdentityAssessment
        )
        names = [item.field_name for item in assessments]
        if set(names) != set(REPLAY_IDENTITY_FIELDS) or len(names) != len(set(names)):
            raise FailureRecoveryReplayError(
                "replay binding must assess every mandatory execution identity exactly once"
            )
        object.__setattr__(
            self, "assessments", tuple(sorted(assessments, key=lambda item: item.field_name))
        )

    @classmethod
    def from_identities(
        cls,
        *,
        evidence_snapshot_identity: str | None,
        factory_source_identity: str | None,
        governance_snapshot_identity: str | None,
        requirement_identity: str | None,
        tool_config_identity: str | None,
        unmeasured_fields: Iterable[str] = (),
    ) -> "ReplayIdentityBinding":
        unmeasured = frozenset(unmeasured_fields)
        if not unmeasured.issubset(REPLAY_IDENTITY_FIELDS):
            raise FailureRecoveryReplayError("unmeasured replay identity field is unsupported")
        values = {
            "evidence_snapshot_identity": evidence_snapshot_identity,
            "factory_source_identity": factory_source_identity,
            "governance_snapshot_identity": governance_snapshot_identity,
            "requirement_identity": requirement_identity,
            "tool_config_identity": tool_config_identity,
        }
        assessments = []
        for field_name in REPLAY_IDENTITY_FIELDS:
            identity = values[field_name]
            if field_name in unmeasured:
                verdict = ProofVerdict.NOT_MEASURED
                identity = None
            elif identity is None or _missing_identity(identity):
                verdict = ProofVerdict.UNKNOWN
            else:
                verdict = ProofVerdict.PROVEN
            assessments.append(ReplayIdentityAssessment(field_name, verdict, identity))
        return cls(tuple(assessments))

    @classmethod
    def from_execution_fingerprint(
        cls, fingerprint: ExecutionFingerprint
    ) -> "ReplayIdentityBinding":
        if not isinstance(fingerprint, ExecutionFingerprint):
            raise FailureRecoveryReplayError(
                "fingerprint must use the M2.5 ExecutionFingerprint"
            )
        return cls.from_identities(
            evidence_snapshot_identity=fingerprint.evidence_snapshot_identity,
            factory_source_identity=fingerprint.factory_source_identity,
            governance_snapshot_identity=fingerprint.governance_snapshot_identity,
            requirement_identity=fingerprint.requirement_identity,
            tool_config_identity=fingerprint.tool_config_identity,
        )

    @property
    def all_proven(self) -> bool:
        return all(item.verdict is ProofVerdict.PROVEN for item in self.assessments)

    def identity_for(self, field_name: str) -> str | None:
        if field_name not in REPLAY_IDENTITY_FIELDS:
            raise FailureRecoveryReplayError("replay identity field is unsupported")
        return next(
            item.identity for item in self.assessments if item.field_name == field_name
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "assessments": [item.to_dict() for item in self.assessments],
            "schema_version": self.SCHEMA_VERSION,
        }

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def binding_id(self) -> str:
        return f"REPLAY-IDENTITY-BINDING-{self.binding_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "binding_id": self.binding_id,
            "binding_sha256": self.binding_sha256,
        }


@dataclass(frozen=True)
class FaultInjectionRecord:
    """Canonical observation of the exact injected filesystem fault."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.fault-injection-record.v1"

    scenario_id: str
    execution_fingerprint_id: str
    fault_class: FaultClass
    mechanism: FaultMechanism
    target_before: ArtifactIdentity
    target_after: ArtifactIdentity
    quarantine_artifact: ArtifactIdentity

    def __post_init__(self) -> None:
        _stable_identifier(self.scenario_id, "scenario_id")
        _stable_identifier(self.execution_fingerprint_id, "execution_fingerprint_id")
        if not isinstance(self.fault_class, FaultClass):
            raise FailureRecoveryReplayError("fault_class must use FaultClass")
        if not isinstance(self.mechanism, FaultMechanism):
            raise FailureRecoveryReplayError("mechanism must use FaultMechanism")
        for field_name in ("target_before", "target_after", "quarantine_artifact"):
            if not isinstance(getattr(self, field_name), ArtifactIdentity):
                raise FailureRecoveryReplayError(
                    f"{field_name} must use ArtifactIdentity"
                )
        if self.target_before.role is not ArtifactRole.EXECUTION_OUTPUT:
            raise FailureRecoveryReplayError("fault target must be an execution output")
        if self.target_before.availability is not ArtifactAvailability.PRESENT:
            raise FailureRecoveryReplayError("fault target must exist before injection")
        if (
            self.target_after.logical_path != self.target_before.logical_path
            or self.target_after.role is not ArtifactRole.EXECUTION_OUTPUT
            or self.target_after.availability is not ArtifactAvailability.MISSING
        ):
            raise FailureRecoveryReplayError(
                "injected output-loss fault must leave the declared target missing"
            )
        if (
            self.quarantine_artifact.role is not ArtifactRole.EXECUTION_OUTPUT
            or self.quarantine_artifact.availability is not ArtifactAvailability.PRESENT
            or self.quarantine_artifact.sha256 != self.target_before.sha256
            or self.quarantine_artifact.size_bytes != self.target_before.size_bytes
        ):
            raise FailureRecoveryReplayError(
                "quarantine must preserve the exact pre-fault artifact bytes"
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_effects": {
                "gate_weakening": False,
                "governance_pin_mutation": False,
                "requirement_mutation": False,
            },
            "execution_fingerprint_id": self.execution_fingerprint_id,
            "fault_class": self.fault_class.value,
            "mechanism": self.mechanism.value,
            "quarantine_artifact": self.quarantine_artifact.to_dict(),
            "scenario_id": self.scenario_id,
            "schema_version": self.SCHEMA_VERSION,
            "target_after": self.target_after.to_dict(),
            "target_before": self.target_before.to_dict(),
        }

    @property
    def injection_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def injection_id(self) -> str:
        return f"FAULT-INJECTION-{self.injection_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "injection_id": self.injection_id,
            "injection_sha256": self.injection_sha256,
        }


@dataclass(frozen=True)
class FailureFinding:
    """One ordered, typed comparison supporting an operational diagnosis."""

    sequence: int
    check_id: str
    verdict: ProofVerdict
    authority_fact_id: str
    expected: Any
    observed: Any
    explanation: str

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise FailureRecoveryReplayError("finding sequence must be non-negative")
        _stable_identifier(self.check_id, "check_id")
        _stable_identifier(self.authority_fact_id, "authority_fact_id")
        _stable_text(self.explanation, "explanation")
        if self.verdict not in {ProofVerdict.PROVEN, ProofVerdict.DISPROVEN}:
            raise FailureRecoveryReplayError(
                "failure findings must use PROVEN or DISPROVEN"
            )
        object.__setattr__(self, "expected", json.loads(canonical_json(self.expected)))
        object.__setattr__(self, "observed", json.loads(canonical_json(self.observed)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_fact_id": self.authority_fact_id,
            "check_id": self.check_id,
            "expected": self.expected,
            "explanation": self.explanation,
            "observed": self.observed,
            "sequence": self.sequence,
            "verdict": self.verdict.value,
        }


@dataclass(frozen=True)
class FailureRecord:
    """Authenticated diagnosis that retains, rather than replaces, failed evidence."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.operational-failure-record.v1"

    source_evidence_id: str
    source_evidence_sha256: str
    injection_id: str
    failure_class: FailureClass
    findings: tuple[FailureFinding, ...]

    def __post_init__(self) -> None:
        _stable_identifier(self.source_evidence_id, "source_evidence_id")
        _stable_identifier(self.injection_id, "injection_id")
        if not _is_sha256(self.source_evidence_sha256):
            raise FailureRecoveryReplayError("source evidence digest must be SHA-256")
        if not isinstance(self.failure_class, FailureClass):
            raise FailureRecoveryReplayError("failure_class must use FailureClass")
        findings = _record_collection(self.findings, "findings", FailureFinding)
        if not findings:
            raise FailureRecoveryReplayError("failure record requires findings")
        sequences = [item.sequence for item in findings]
        check_ids = [item.check_id for item in findings]
        if len(sequences) != len(set(sequences)) or len(check_ids) != len(set(check_ids)):
            raise FailureRecoveryReplayError("failure findings must be uniquely ordered")
        findings = tuple(sorted(findings, key=lambda item: item.sequence))
        if not any(item.verdict is ProofVerdict.DISPROVEN for item in findings):
            raise FailureRecoveryReplayError(
                "failure record requires at least one evidence-derived disproof"
            )
        object.__setattr__(self, "findings", findings)

    @property
    def first_authoritative_failure(self) -> FailureFinding:
        return next(item for item in self.findings if item.verdict is ProofVerdict.DISPROVEN)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "diagnosis_verdict": ProofVerdict.PROVEN.value,
            "failed_evidence_preserved": True,
            "failure_class": self.failure_class.value,
            "findings": [item.to_dict() for item in self.findings],
            "first_authoritative_failure": self.first_authoritative_failure.to_dict(),
            "injection_id": self.injection_id,
            "schema_version": self.SCHEMA_VERSION,
            "source_evidence_id": self.source_evidence_id,
            "source_evidence_sha256": self.source_evidence_sha256,
        }

    @property
    def failure_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def failure_id(self) -> str:
        return f"OPERATIONAL-FAILURE-{self.failure_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "failure_id": self.failure_id,
            "failure_sha256": self.failure_sha256,
        }


@dataclass(frozen=True)
class RecoveryDecision:
    """Deterministic, non-authoritative decision from replay identity knowledge."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.recovery-decision.v1"

    failure_id: str
    replay_binding: ReplayIdentityBinding
    action: RecoveryAction = field(init=False)
    verdict: ProofVerdict = field(init=False)

    def __post_init__(self) -> None:
        _stable_identifier(self.failure_id, "failure_id")
        if not isinstance(self.replay_binding, ReplayIdentityBinding):
            raise FailureRecoveryReplayError(
                "replay_binding must use ReplayIdentityBinding"
            )
        if self.replay_binding.all_proven:
            action = RecoveryAction.REPLAY_EXACT_BOUND_INPUTS
            verdict = ProofVerdict.PROVEN
        else:
            action = RecoveryAction.STOP_MISSING_IDENTITY
            verdict = ProofVerdict.UNKNOWN
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "verdict", verdict)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "authority_boundary": {
                "decision_role": "DETERMINISTIC_LOCAL_RECOVERY_PROJECTION",
                "governance_authority": "NONE",
                "human_gate_required": True,
            },
            "failure_id": self.failure_id,
            "prohibitions": {
                "erase_failure_evidence": True,
                "gate_weakening": True,
                "governance_pin_mutation": True,
                "requirement_mutation": True,
            },
            "replay_binding": self.replay_binding.to_dict(),
            "schema_version": self.SCHEMA_VERSION,
            "verdict": self.verdict.value,
        }

    @property
    def decision_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def decision_id(self) -> str:
        return f"RECOVERY-DECISION-{self.decision_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "decision_id": self.decision_id,
            "decision_sha256": self.decision_sha256,
        }


def build_recovery_decision(
    failure_id: str, replay_binding: ReplayIdentityBinding
) -> RecoveryDecision:
    """Derive a fail-closed recovery action without caller-supplied authority."""
    return RecoveryDecision(failure_id=failure_id, replay_binding=replay_binding)


@dataclass(frozen=True)
class ReplayCheck:
    """One exact comparison used to derive the replay verdict."""

    check_id: str
    verdict: ProofVerdict
    expected: Any
    observed: Any
    explanation: str

    def __post_init__(self) -> None:
        _stable_identifier(self.check_id, "check_id")
        _stable_text(self.explanation, "explanation")
        if self.verdict not in {
            ProofVerdict.PROVEN,
            ProofVerdict.DISPROVEN,
            ProofVerdict.UNKNOWN,
            ProofVerdict.NOT_MEASURED,
        }:
            raise FailureRecoveryReplayError("replay check verdict is unsupported")
        object.__setattr__(self, "expected", json.loads(canonical_json(self.expected)))
        object.__setattr__(self, "observed", json.loads(canonical_json(self.observed)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "expected": self.expected,
            "explanation": self.explanation,
            "observed": self.observed,
            "verdict": self.verdict.value,
        }


@dataclass(frozen=True)
class ReplayRecord:
    """Evidence-derived result of exact-input replay, including negative outcomes."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.deterministic-replay-record.v1"

    failure_id: str
    decision_id: str
    action: RecoveryAction
    source_evidence_id: str
    replay_evidence_id: str | None
    checks: tuple[ReplayCheck, ...]
    limitations: tuple[str, ...]
    verdict: ProofVerdict = field(init=False)

    def __post_init__(self) -> None:
        for field_name in ("failure_id", "decision_id", "source_evidence_id"):
            _stable_identifier(getattr(self, field_name), field_name)
        if self.replay_evidence_id is not None:
            _stable_identifier(self.replay_evidence_id, "replay_evidence_id")
        if not isinstance(self.action, RecoveryAction):
            raise FailureRecoveryReplayError("action must use RecoveryAction")
        checks = _record_collection(self.checks, "checks", ReplayCheck)
        ids = [item.check_id for item in checks]
        if len(ids) != len(set(ids)):
            raise FailureRecoveryReplayError("replay check IDs must be unique")
        checks = tuple(sorted(checks, key=lambda item: item.check_id))
        if self.action is RecoveryAction.REPLAY_EXACT_BOUND_INPUTS:
            if self.replay_evidence_id is None or not checks:
                raise FailureRecoveryReplayError(
                    "executed replay requires evidence and deterministic checks"
                )
            verdict = (
                ProofVerdict.PROVEN
                if all(item.verdict is ProofVerdict.PROVEN for item in checks)
                else ProofVerdict.DISPROVEN
            )
        else:
            if self.replay_evidence_id is not None:
                raise FailureRecoveryReplayError(
                    "blocked replay cannot carry invented execution evidence"
                )
            if any(item.verdict is ProofVerdict.PROVEN for item in checks):
                raise FailureRecoveryReplayError(
                    "blocked replay checks cannot claim execution proof"
                )
            verdict = ProofVerdict.NOT_MEASURED
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "limitations", _normalized_limitations(self.limitations))
        object.__setattr__(self, "verdict", verdict)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "checks": [item.to_dict() for item in self.checks],
            "decision_id": self.decision_id,
            "failure_evidence_preserved": True,
            "failure_id": self.failure_id,
            "limitations": list(self.limitations),
            "replay_evidence_id": self.replay_evidence_id,
            "schema_version": self.SCHEMA_VERSION,
            "source_evidence_id": self.source_evidence_id,
            "verdict": self.verdict.value,
        }

    @property
    def replay_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def replay_id(self) -> str:
        return f"DETERMINISTIC-REPLAY-{self.replay_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "replay_id": self.replay_id,
            "replay_sha256": self.replay_sha256,
        }


def _comparison(
    check_id: str,
    expected: Any,
    observed: Any,
    explanation: str,
) -> ReplayCheck:
    return ReplayCheck(
        check_id=check_id,
        verdict=(
            ProofVerdict.PROVEN if expected == observed else ProofVerdict.DISPROVEN
        ),
        expected=expected,
        observed=observed,
        explanation=explanation,
    )


@dataclass(frozen=True)
class FailureRecoveryReplayEvidence:
    """Canonical envelope retaining the failure and the separate replay proof."""

    SCHEMA_VERSION: ClassVar[str] = (
        "upi_app_factory.failure-recovery-replay-evidence.v1"
    )

    source_acceptance_evidence: OperationalAcceptanceEvidence
    fault_injection: FaultInjectionRecord
    failure_record: FailureRecord
    recovery_decision: RecoveryDecision
    replay_acceptance_evidence: OperationalAcceptanceEvidence | None
    replay_record: ReplayRecord
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_acceptance_evidence, OperationalAcceptanceEvidence
        ):
            raise FailureRecoveryReplayError(
                "source_acceptance_evidence must use OperationalAcceptanceEvidence"
            )
        if not isinstance(self.fault_injection, FaultInjectionRecord):
            raise FailureRecoveryReplayError(
                "fault_injection must use FaultInjectionRecord"
            )
        if not isinstance(self.failure_record, FailureRecord):
            raise FailureRecoveryReplayError("failure_record must use FailureRecord")
        if not isinstance(self.recovery_decision, RecoveryDecision):
            raise FailureRecoveryReplayError(
                "recovery_decision must use RecoveryDecision"
            )
        if self.replay_acceptance_evidence is not None and not isinstance(
            self.replay_acceptance_evidence, OperationalAcceptanceEvidence
        ):
            raise FailureRecoveryReplayError(
                "replay_acceptance_evidence must use OperationalAcceptanceEvidence"
            )
        if not isinstance(self.replay_record, ReplayRecord):
            raise FailureRecoveryReplayError("replay_record must use ReplayRecord")
        source = self.source_acceptance_evidence
        if source.evidence_id != self.failure_record.source_evidence_id:
            raise FailureRecoveryReplayError("failure record must bind source evidence")
        if source.evidence_sha256 != self.failure_record.source_evidence_sha256:
            raise FailureRecoveryReplayError("failure record source digest is invalid")
        if self.fault_injection.injection_id != self.failure_record.injection_id:
            raise FailureRecoveryReplayError("failure record must bind fault injection")
        if self.failure_record.failure_id != self.recovery_decision.failure_id:
            raise FailureRecoveryReplayError("recovery decision must bind failure record")
        if self.recovery_decision.decision_id != self.replay_record.decision_id:
            raise FailureRecoveryReplayError("replay record must bind recovery decision")
        if self.failure_record.failure_id != self.replay_record.failure_id:
            raise FailureRecoveryReplayError("replay record must retain failure identity")
        if source.evidence_id != self.replay_record.source_evidence_id:
            raise FailureRecoveryReplayError("replay record must bind source evidence")
        if self.replay_acceptance_evidence is None:
            if self.replay_record.replay_evidence_id is not None:
                raise FailureRecoveryReplayError("replay evidence identity is inconsistent")
        elif (
            self.replay_record.replay_evidence_id
            != self.replay_acceptance_evidence.evidence_id
        ):
            raise FailureRecoveryReplayError("replay record must bind replay evidence")
        object.__setattr__(self, "limitations", _normalized_limitations(self.limitations))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_boundary": {
                "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
                "ai_authority": "NONE",
                "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
                "self_awarded_recovery_authority": False,
            },
            "failure_record": self.failure_record.to_dict(),
            "fault_injection": self.fault_injection.to_dict(),
            "identity_scope": "CANONICAL_FAILURE_AND_REPLAY_CORE",
            "limitations": list(self.limitations),
            "recovery_decision": self.recovery_decision.to_dict(),
            "replay_acceptance_evidence": (
                self.replay_acceptance_evidence.to_dict()
                if self.replay_acceptance_evidence is not None
                else None
            ),
            "replay_record": self.replay_record.to_dict(),
            "schema_version": self.SCHEMA_VERSION,
            "source_acceptance_evidence": self.source_acceptance_evidence.to_dict(),
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def evidence_id(self) -> str:
        return f"FAILURE-RECOVERY-REPLAY-EVIDENCE-{self.evidence_sha256}"

    @property
    def provenance_binding(self) -> ProvenanceBinding:
        return ProvenanceBinding(
            source_id=f"SOURCE-FAILURE-RECOVERY-REPLAY-{self.evidence_sha256}",
            revision=(
                self.source_acceptance_evidence.scenario.execution_fingerprint.fingerprint_id
            ),
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
        """Project the observed outcome into M2.4 facts without granting authority."""
        return FactNode(
            node_id=f"FACT-FAILURE-RECOVERY-REPLAY-{self.evidence_sha256}",
            node_type="AUTHENTICATED_MACHINE_EVIDENCE",
            status=FactStatus.PROVEN,
            value={
                "evidence_id": self.evidence_id,
                "failure_class": self.failure_record.failure_class.value,
                "first_authoritative_failure": (
                    self.failure_record.first_authoritative_failure.check_id
                ),
                "replay_verdict": self.replay_record.verdict.value,
            },
            provenance=(self.provenance_binding,),
            metadata={
                "authority": "MACHINE_OBSERVATION_ONLY",
                "limitations": list(self.limitations),
            },
        )

    def evidence_graph(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=(self.machine_evidence_fact(),))


def _quarantine_path(logical_path: str) -> str:
    normalized = _logical_path(logical_path, "fault target")
    return _logical_path(
        f"{QUARANTINE_PREFIX}/{normalized}", "quarantine artifact path"
    )


def _ensure_distinct_workspaces(
    project_root: Path, failure_workspace: Path, replay_workspace: Path
) -> None:
    project = project_root.resolve()
    failure = failure_workspace.resolve()
    replay = replay_workspace.resolve()
    if failure == replay:
        raise FailureRecoveryReplayError(
            "failure and replay require distinct disposable workspaces"
        )
    for workspace in (failure, replay):
        if workspace == project or project in workspace.parents or workspace in project.parents:
            raise FailureRecoveryReplayError(
                "failure and replay workspaces must be isolated from source"
            )


def run_failure_recovery_replay(
    project_root: Path,
    failure_workspace: Path,
    replay_workspace: Path,
) -> FailureRecoveryReplayEvidence:
    """Inject output loss, diagnose it, and replay the exact bound local scenario."""
    root = project_root.resolve()
    _ensure_distinct_workspaces(root, failure_workspace, replay_workspace)
    source_evidence = run_representative_operational_acceptance(
        root, failure_workspace
    )
    if source_evidence.result.status is not AcceptanceStatus.PASS:
        raise FailureRecoveryReplayError(
            "fault injection requires a passing bound acceptance observation"
        )
    validate_operational_acceptance_evidence(source_evidence.to_dict())
    if len(source_evidence.result.output_artifacts) != 1:
        raise FailureRecoveryReplayError(
            "representative fault injection requires exactly one declared output"
        )
    target_before = source_evidence.result.output_artifacts[0]
    if target_before.availability is not ArtifactAvailability.PRESENT:
        raise FailureRecoveryReplayError("declared output is unavailable before injection")

    target_path = failure_workspace / PurePosixPath(target_before.logical_path)
    quarantine_logical_path = _quarantine_path(target_before.logical_path)
    quarantine_path = failure_workspace / PurePosixPath(quarantine_logical_path)
    if target_path.is_symlink() or quarantine_path.exists():
        raise FailureRecoveryReplayError("fault target or quarantine path is unsafe")
    quarantine_path.parent.mkdir(parents=True, exist_ok=False)
    target_path.replace(quarantine_path)

    target_after = ArtifactIdentity.observe(
        failure_workspace,
        target_before.logical_path,
        ArtifactRole.EXECUTION_OUTPUT,
    )
    quarantine_artifact = ArtifactIdentity.observe(
        failure_workspace,
        quarantine_logical_path,
        ArtifactRole.EXECUTION_OUTPUT,
    )
    injection = FaultInjectionRecord(
        scenario_id=source_evidence.scenario.scenario_id,
        execution_fingerprint_id=(
            source_evidence.scenario.execution_fingerprint.fingerprint_id
        ),
        fault_class=FaultClass.EXECUTION_OUTPUT_UNAVAILABLE,
        mechanism=FaultMechanism.QUARANTINE_DECLARED_OUTPUT,
        target_before=target_before,
        target_after=target_after,
        quarantine_artifact=quarantine_artifact,
    )
    finding = FailureFinding(
        sequence=0,
        check_id="OUTPUT-ARTIFACT-IDENTITY",
        verdict=(
            ProofVerdict.DISPROVEN
            if target_after.to_dict() != target_before.to_dict()
            else ProofVerdict.PROVEN
        ),
        authority_fact_id=source_evidence.machine_evidence_fact().node_id,
        expected=target_before.to_dict(),
        observed=target_after.to_dict(),
        explanation=(
            "The declared execution output no longer matches the authenticated "
            "pre-fault artifact identity."
        ),
    )
    failure = FailureRecord(
        source_evidence_id=source_evidence.evidence_id,
        source_evidence_sha256=source_evidence.evidence_sha256,
        injection_id=injection.injection_id,
        failure_class=FailureClass.EVIDENCE_INTEGRITY_FAILURE,
        findings=(finding,),
    )
    binding = ReplayIdentityBinding.from_execution_fingerprint(
        source_evidence.scenario.execution_fingerprint
    )
    decision = build_recovery_decision(failure.failure_id, binding)

    replay_evidence: OperationalAcceptanceEvidence | None = None
    replay_checks: tuple[ReplayCheck, ...]
    if decision.action is RecoveryAction.REPLAY_EXACT_BOUND_INPUTS:
        replay_evidence = run_representative_operational_acceptance(
            root, replay_workspace
        )
        validate_operational_acceptance_evidence(replay_evidence.to_dict())
        source_fingerprint = source_evidence.scenario.execution_fingerprint
        replay_fingerprint = replay_evidence.scenario.execution_fingerprint
        replay_checks = (
            _comparison(
                "ACCEPTANCE-RESULT-IDENTITY",
                source_evidence.result.result_id,
                replay_evidence.result.result_id,
                "Exact inputs must reproduce the canonical acceptance result identity.",
            ),
            _comparison(
                "ACCEPTANCE-STATUS",
                AcceptanceStatus.PASS.value,
                replay_evidence.result.status.value,
                "Recovery replay must satisfy the unchanged acceptance gates.",
            ),
            _comparison(
                "EVIDENCE-INPUT-IDENTITY",
                source_fingerprint.evidence_snapshot_identity,
                replay_fingerprint.evidence_snapshot_identity,
                "Replay must retain the exact evidence-input identity.",
            ),
            _comparison(
                "EXECUTION-FINGERPRINT-IDENTITY",
                source_fingerprint.fingerprint_id,
                replay_fingerprint.fingerprint_id,
                "Replay must retain the complete M2.5 execution fingerprint.",
            ),
            _comparison(
                "FACTORY-SOURCE-IDENTITY",
                source_fingerprint.factory_source_identity,
                replay_fingerprint.factory_source_identity,
                "Replay must not silently select different factory source.",
            ),
            _comparison(
                "GOVERNANCE-PIN-IDENTITY",
                source_fingerprint.governance_snapshot_identity,
                replay_fingerprint.governance_snapshot_identity,
                "Replay must not mutate or promote the bound governance snapshot.",
            ),
            _comparison(
                "OUTPUT-ARTIFACT-IDENTITIES",
                [item.to_dict() for item in source_evidence.result.output_artifacts],
                [item.to_dict() for item in replay_evidence.result.output_artifacts],
                "Replay outputs must reproduce exact content identities.",
            ),
            _comparison(
                "REQUIREMENT-IDENTITY",
                source_fingerprint.requirement_identity,
                replay_fingerprint.requirement_identity,
                "Replay must not silently change the requirement input.",
            ),
            _comparison(
                "SCENARIO-IDENTITY",
                source_evidence.scenario.scenario_id,
                replay_evidence.scenario.scenario_id,
                "Replay must execute the same canonical scenario.",
            ),
            _comparison(
                "TOOL-CONFIG-IDENTITY",
                source_fingerprint.tool_config_identity,
                replay_fingerprint.tool_config_identity,
                "Replay must retain the exact command and environment contract.",
            ),
            _comparison(
                "VALIDATION-GATES",
                [item.to_dict() for item in source_evidence.result.checks],
                [item.to_dict() for item in replay_evidence.result.checks],
                "Recovery cannot drop or weaken an acceptance check.",
            ),
        )
    else:
        replay_checks = tuple(
            ReplayCheck(
                check_id=f"IDENTITY-{item.field_name.upper().replace('_', '-')}",
                verdict=item.verdict,
                expected="EXACT_BOUND_IDENTITY",
                observed=item.identity,
                explanation="Replay is stopped when a mandatory identity is unknown.",
            )
            for item in binding.assessments
            if item.verdict is not ProofVerdict.PROVEN
        )

    replay_record = ReplayRecord(
        failure_id=failure.failure_id,
        decision_id=decision.decision_id,
        action=decision.action,
        source_evidence_id=source_evidence.evidence_id,
        replay_evidence_id=(
            replay_evidence.evidence_id if replay_evidence is not None else None
        ),
        checks=replay_checks,
        limitations=(
            "Recovery proof covers only the declared local requirements-compiler scenario.",
            "The injected fault is output unavailability; other incident classes are not measured.",
            "No deployment, production, certification, regulatory, security, or "
            "performance authority is granted.",
        ),
    )
    return FailureRecoveryReplayEvidence(
        source_acceptance_evidence=source_evidence,
        fault_injection=injection,
        failure_record=failure,
        recovery_decision=decision,
        replay_acceptance_evidence=replay_evidence,
        replay_record=replay_record,
        limitations=(
            "External payment ecosystems remain mocked or simulated and are not exercised.",
            "Failure evidence and quarantined bytes remain in the original disposable workspace.",
            "Only deterministic local replay is observed; supervisor and human "
            "gates retain authority.",
        ),
    )


def _artifact_document_is_present(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("availability") == ArtifactAvailability.PRESENT.value
        and _is_sha256(value.get("sha256"))
        and isinstance(value.get("size_bytes"), int)
        and cast(int, value.get("size_bytes")) >= 0
    )


def validate_failure_recovery_replay_evidence(document: Mapping[str, Any]) -> bool:
    """Fail closed on tampering, missing identity, or weakened replay semantics."""
    if not isinstance(document, Mapping):
        raise FailureRecoveryReplayError("failure/replay evidence must be a JSON object")
    value = cast(dict[str, Any], json.loads(canonical_json(dict(document))))
    expected_fields = {
        "authority_boundary",
        "evidence_id",
        "evidence_sha256",
        "failure_record",
        "fault_injection",
        "identity_scope",
        "limitations",
        "provenance",
        "recovery_decision",
        "replay_acceptance_evidence",
        "replay_record",
        "schema_version",
        "source_acceptance_evidence",
    }
    if set(value) != expected_fields:
        raise FailureRecoveryReplayError("failure/replay evidence fields are invalid")
    if value.get("schema_version") != FailureRecoveryReplayEvidence.SCHEMA_VERSION:
        raise FailureRecoveryReplayError("failure/replay schema version is unsupported")
    if value.get("identity_scope") != "CANONICAL_FAILURE_AND_REPLAY_CORE":
        raise FailureRecoveryReplayError("failure/replay identity scope is invalid")
    forbidden_time_keys = {
        "created_at",
        "generated_at",
        "timestamp",
        "updated_at",
        "wall_clock_time",
    }
    if forbidden_time_keys.intersection(_walk_keys(value)):
        raise FailureRecoveryReplayError(
            "wall-clock fields must not destabilize failure/replay identity"
        )
    if value.get("authority_boundary") != {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "AUTHENTICATED_MACHINE_OBSERVATION",
        "self_awarded_recovery_authority": False,
    }:
        raise FailureRecoveryReplayError("failure/replay authority boundary is invalid")

    source = value.get("source_acceptance_evidence")
    replay = value.get("replay_acceptance_evidence")
    injection = value.get("fault_injection")
    failure = value.get("failure_record")
    decision = value.get("recovery_decision")
    replay_record = value.get("replay_record")
    if not all(
        isinstance(item, Mapping)
        for item in (source, injection, failure, decision, replay_record)
    ):
        raise FailureRecoveryReplayError("failure/replay nested records are invalid")
    source_value = cast(Mapping[str, Any], source)
    injection_value = cast(Mapping[str, Any], injection)
    failure_value = cast(Mapping[str, Any], failure)
    decision_value = cast(Mapping[str, Any], decision)
    replay_record_value = cast(Mapping[str, Any], replay_record)
    validate_operational_acceptance_evidence(source_value)
    if replay is not None:
        if not isinstance(replay, Mapping):
            raise FailureRecoveryReplayError("replay acceptance evidence is invalid")
        validate_operational_acceptance_evidence(cast(Mapping[str, Any], replay))

    nested_identities = (
        (
            injection_value,
            "injection_id",
            "injection_sha256",
            "FAULT-INJECTION-",
            FaultInjectionRecord.SCHEMA_VERSION,
        ),
        (
            failure_value,
            "failure_id",
            "failure_sha256",
            "OPERATIONAL-FAILURE-",
            FailureRecord.SCHEMA_VERSION,
        ),
        (
            decision_value,
            "decision_id",
            "decision_sha256",
            "RECOVERY-DECISION-",
            RecoveryDecision.SCHEMA_VERSION,
        ),
        (
            replay_record_value,
            "replay_id",
            "replay_sha256",
            "DETERMINISTIC-REPLAY-",
            ReplayRecord.SCHEMA_VERSION,
        ),
    )
    for nested, id_field, digest_field, prefix, schema_version in nested_identities:
        if nested.get("schema_version") != schema_version:
            raise FailureRecoveryReplayError("nested record schema is unsupported")
        _validate_identity_record(
            nested, id_field=id_field, digest_field=digest_field, prefix=prefix
        )
    binding = decision_value.get("replay_binding")
    if not isinstance(binding, Mapping):
        raise FailureRecoveryReplayError("replay identity binding is missing")
    binding_value = cast(Mapping[str, Any], binding)
    if binding_value.get("schema_version") != ReplayIdentityBinding.SCHEMA_VERSION:
        raise FailureRecoveryReplayError("replay identity binding schema is unsupported")
    _validate_identity_record(
        binding_value,
        id_field="binding_id",
        digest_field="binding_sha256",
        prefix="REPLAY-IDENTITY-BINDING-",
    )

    source_id = source_value.get("evidence_id")
    source_digest = source_value.get("evidence_sha256")
    if (
        failure_value.get("source_evidence_id") != source_id
        or failure_value.get("source_evidence_sha256") != source_digest
        or failure_value.get("injection_id") != injection_value.get("injection_id")
        or decision_value.get("failure_id") != failure_value.get("failure_id")
        or replay_record_value.get("failure_id") != failure_value.get("failure_id")
        or replay_record_value.get("decision_id") != decision_value.get("decision_id")
        or replay_record_value.get("source_evidence_id") != source_id
    ):
        raise FailureRecoveryReplayError("failure/replay record lineage is invalid")
    if failure_value.get("failed_evidence_preserved") is not True:
        raise FailureRecoveryReplayError("failed evidence must remain preserved")
    source_scenario = source_value.get("scenario")
    source_result = source_value.get("result")
    if not isinstance(source_scenario, Mapping) or not isinstance(
        source_result, Mapping
    ):
        raise FailureRecoveryReplayError("source acceptance structure is invalid")
    source_fingerprint = source_scenario.get("execution_fingerprint")
    if not isinstance(source_fingerprint, Mapping):
        raise FailureRecoveryReplayError("source execution fingerprint is missing")
    if (
        injection_value.get("scenario_id") != source_scenario.get("scenario_id")
        or injection_value.get("execution_fingerprint_id")
        != source_fingerprint.get("fingerprint_id")
        or injection_value.get("fault_class")
        != FaultClass.EXECUTION_OUTPUT_UNAVAILABLE.value
        or injection_value.get("mechanism")
        != FaultMechanism.QUARANTINE_DECLARED_OUTPUT.value
    ):
        raise FailureRecoveryReplayError("fault injection source binding is invalid")
    if (
        failure_value.get("failure_class")
        != FailureClass.EVIDENCE_INTEGRITY_FAILURE.value
        or failure_value.get("diagnosis_verdict") != ProofVerdict.PROVEN.value
    ):
        raise FailureRecoveryReplayError("failure diagnosis classification is invalid")
    effects = injection_value.get("authority_effects")
    if effects != {
        "gate_weakening": False,
        "governance_pin_mutation": False,
        "requirement_mutation": False,
    }:
        raise FailureRecoveryReplayError("fault injection changed governed authority")
    if decision_value.get("prohibitions") != {
        "erase_failure_evidence": True,
        "gate_weakening": True,
        "governance_pin_mutation": True,
        "requirement_mutation": True,
    }:
        raise FailureRecoveryReplayError("recovery prohibitions are invalid")

    before = injection_value.get("target_before")
    after = injection_value.get("target_after")
    quarantined = injection_value.get("quarantine_artifact")
    if not _artifact_document_is_present(before) or not _artifact_document_is_present(
        quarantined
    ):
        raise FailureRecoveryReplayError("fault artifact identity is invalid")
    if not isinstance(after, Mapping) or after.get("availability") != "MISSING":
        raise FailureRecoveryReplayError("fault did not make the target unavailable")
    before_value = cast(Mapping[str, Any], before)
    quarantine_value = cast(Mapping[str, Any], quarantined)
    source_outputs = source_result.get("output_artifacts")
    if not isinstance(source_outputs, list) or dict(before_value) not in source_outputs:
        raise FailureRecoveryReplayError(
            "fault target is not an authenticated source output"
        )
    if (
        after.get("logical_path") != before_value.get("logical_path")
        or quarantine_value.get("sha256") != before_value.get("sha256")
        or quarantine_value.get("size_bytes") != before_value.get("size_bytes")
    ):
        raise FailureRecoveryReplayError("quarantined fault bytes are not preserved")
    findings = failure_value.get("findings")
    first = failure_value.get("first_authoritative_failure")
    if (
        not isinstance(findings, list)
        or not findings
        or first != next(
            (item for item in findings if item.get("verdict") == "DISPROVEN"), None
        )
        or not isinstance(first, Mapping)
        or first.get("sequence") != 0
        or first.get("check_id") != "OUTPUT-ARTIFACT-IDENTITY"
        or first.get("authority_fact_id")
        != f"FACT-OPERATIONAL-ACCEPTANCE-{source_digest}"
        or first.get("expected") != before
        or first.get("observed") != after
    ):
        raise FailureRecoveryReplayError("first authoritative failure is invalid")

    assessments = binding_value.get("assessments")
    if not isinstance(assessments, list) or len(assessments) != len(
        REPLAY_IDENTITY_FIELDS
    ):
        raise FailureRecoveryReplayError("replay identity assessments are incomplete")
    assessment_by_name = {
        item.get("field_name"): item for item in assessments if isinstance(item, Mapping)
    }
    if set(assessment_by_name) != set(REPLAY_IDENTITY_FIELDS):
        raise FailureRecoveryReplayError("replay identity assessments are ambiguous")
    fingerprint = source_fingerprint
    all_proven = True
    for field_name in REPLAY_IDENTITY_FIELDS:
        assessment = assessment_by_name[field_name]
        identity = assessment.get("identity")
        verdict = assessment.get("verdict")
        if identity != fingerprint.get(field_name):
            raise FailureRecoveryReplayError("replay binding changed a source identity")
        expected_verdict = (
            "UNKNOWN"
            if not isinstance(identity, str) or _missing_identity(identity)
            else "PROVEN"
        )
        if verdict != expected_verdict:
            raise FailureRecoveryReplayError("replay identity verdict is invalid")
        all_proven = all_proven and verdict == "PROVEN"
    expected_action = (
        RecoveryAction.REPLAY_EXACT_BOUND_INPUTS.value
        if all_proven
        else RecoveryAction.STOP_MISSING_IDENTITY.value
    )
    if decision_value.get("action") != expected_action:
        raise FailureRecoveryReplayError("recovery action is not identity-derived")
    expected_decision_verdict = "PROVEN" if all_proven else "UNKNOWN"
    if (
        decision_value.get("verdict") != expected_decision_verdict
        or decision_value.get("authority_boundary")
        != {
            "decision_role": "DETERMINISTIC_LOCAL_RECOVERY_PROJECTION",
            "governance_authority": "NONE",
            "human_gate_required": True,
        }
    ):
        raise FailureRecoveryReplayError("recovery decision authority is invalid")

    replay_id = replay.get("evidence_id") if isinstance(replay, Mapping) else None
    if replay_record_value.get("replay_evidence_id") != replay_id:
        raise FailureRecoveryReplayError("replay evidence lineage is invalid")
    checks = replay_record_value.get("checks")
    if not isinstance(checks, list):
        raise FailureRecoveryReplayError("replay checks are invalid")
    if expected_action == RecoveryAction.REPLAY_EXACT_BOUND_INPUTS.value:
        if replay is None or not checks:
            raise FailureRecoveryReplayError("exact replay evidence is missing")
        replay_value = cast(Mapping[str, Any], replay)
        replay_scenario = replay_value.get("scenario")
        replay_result = replay_value.get("result")
        if not isinstance(replay_scenario, Mapping) or not isinstance(
            replay_result, Mapping
        ):
            raise FailureRecoveryReplayError("replay acceptance structure is invalid")
        replay_fingerprint = replay_scenario.get("execution_fingerprint")
        if not isinstance(replay_fingerprint, Mapping):
            raise FailureRecoveryReplayError("replay execution fingerprint is missing")
        comparison_values = {
            "ACCEPTANCE-RESULT-IDENTITY": (
                source_result.get("result_id"),
                replay_result.get("result_id"),
            ),
            "ACCEPTANCE-STATUS": (
                AcceptanceStatus.PASS.value,
                replay_result.get("status"),
            ),
            "EVIDENCE-INPUT-IDENTITY": (
                fingerprint.get("evidence_snapshot_identity"),
                replay_fingerprint.get("evidence_snapshot_identity"),
            ),
            "EXECUTION-FINGERPRINT-IDENTITY": (
                fingerprint.get("fingerprint_id"),
                replay_fingerprint.get("fingerprint_id"),
            ),
            "FACTORY-SOURCE-IDENTITY": (
                fingerprint.get("factory_source_identity"),
                replay_fingerprint.get("factory_source_identity"),
            ),
            "GOVERNANCE-PIN-IDENTITY": (
                fingerprint.get("governance_snapshot_identity"),
                replay_fingerprint.get("governance_snapshot_identity"),
            ),
            "OUTPUT-ARTIFACT-IDENTITIES": (
                source_result.get("output_artifacts"),
                replay_result.get("output_artifacts"),
            ),
            "REQUIREMENT-IDENTITY": (
                fingerprint.get("requirement_identity"),
                replay_fingerprint.get("requirement_identity"),
            ),
            "SCENARIO-IDENTITY": (
                source_scenario.get("scenario_id"),
                replay_scenario.get("scenario_id"),
            ),
            "TOOL-CONFIG-IDENTITY": (
                fingerprint.get("tool_config_identity"),
                replay_fingerprint.get("tool_config_identity"),
            ),
            "VALIDATION-GATES": (
                source_result.get("checks"),
                replay_result.get("checks"),
            ),
        }
        check_by_id = {
            item.get("check_id"): item for item in checks if isinstance(item, Mapping)
        }
        if set(check_by_id) != set(comparison_values) or len(check_by_id) != len(checks):
            raise FailureRecoveryReplayError("replay checks are incomplete or ambiguous")
        for check_id, (expected, observed) in comparison_values.items():
            item = check_by_id[check_id]
            derived_verdict = "PROVEN" if expected == observed else "DISPROVEN"
            if (
                item.get("expected") != expected
                or item.get("observed") != observed
                or item.get("verdict") != derived_verdict
            ):
                raise FailureRecoveryReplayError(
                    "replay check is not derived from authenticated evidence"
                )
        expected_replay_verdict = (
            "PROVEN"
            if all(item.get("verdict") == "PROVEN" for item in checks)
            else "DISPROVEN"
        )
    else:
        if replay is not None:
            raise FailureRecoveryReplayError("unknown identity must stop replay")
        expected_replay_verdict = "NOT_MEASURED"
    if replay_record_value.get("verdict") != expected_replay_verdict:
        raise FailureRecoveryReplayError("replay verdict is not evidence-derived")

    evidence_digest = value.get("evidence_sha256")
    core = {
        key: item
        for key, item in value.items()
        if key not in {"evidence_id", "evidence_sha256", "provenance"}
    }
    if not _is_sha256(evidence_digest) or canonical_sha256(core) != evidence_digest:
        raise FailureRecoveryReplayError("failure/replay evidence digest is invalid")
    if value.get("evidence_id") != (
        f"FAILURE-RECOVERY-REPLAY-EVIDENCE-{evidence_digest}"
    ):
        raise FailureRecoveryReplayError("failure/replay evidence ID is invalid")
    expected_provenance = ProvenanceBinding(
        source_id=f"SOURCE-FAILURE-RECOVERY-REPLAY-{evidence_digest}",
        revision=str(fingerprint.get("fingerprint_id")),
        content_sha256=cast(str, evidence_digest),
        source_type="MACHINE_EXECUTION_RECORD",
    ).to_dict()
    if value.get("provenance") != expected_provenance:
        raise FailureRecoveryReplayError("failure/replay provenance is invalid")
    return True


def write_failure_recovery_replay_evidence(
    evidence: FailureRecoveryReplayEvidence, path: Path
) -> dict[str, str]:
    """Write canonical evidence once, without local paths or timestamps."""
    if not isinstance(evidence, FailureRecoveryReplayEvidence):
        raise FailureRecoveryReplayError(
            "evidence must use FailureRecoveryReplayEvidence"
        )
    if path.exists():
        raise FailureRecoveryReplayError(
            "evidence output already exists; use a new disposable output path"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (evidence.to_json() + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return {
        "evidence_id": evidence.evidence_id,
        "file_sha256": _sha256_bytes(encoded),
        "first_authoritative_failure": (
            evidence.failure_record.first_authoritative_failure.check_id
        ),
        "status": evidence.replay_record.verdict.value,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inject, diagnose, recover, and replay local acceptance evidence."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--failure-workspace", type=Path, required=True)
    parser.add_argument("--replay-workspace", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    evidence = run_failure_recovery_replay(
        parsed.project_root,
        parsed.failure_workspace,
        parsed.replay_workspace,
    )
    output_path = parsed.evidence_output or (
        parsed.replay_workspace / "failure_recovery_replay_evidence.json"
    )
    summary = write_failure_recovery_replay_evidence(evidence, output_path)
    summary["evidence_artifact"] = (
        output_path.relative_to(parsed.replay_workspace).as_posix()
        if output_path.is_relative_to(parsed.replay_workspace)
        else "CALLER_SELECTED_OUTPUT"
    )
    print(canonical_json(summary))
    return 0 if evidence.replay_record.verdict is ProofVerdict.PROVEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
