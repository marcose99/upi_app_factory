"""Append-only governed evolution ledger and exact reproduction records.

The ledger seals identities that have already been established by the M2.5
source, impact, and control-plane contracts.  It does not turn observations,
model proposals, or explanations into authority.  Every entry is immutable,
canonically serialized, and linked to its predecessor; the mutable ledger is
only an append coordinator over those sealed values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Iterable, Mapping

from factory.documentation import canonical_json, canonical_sha256

from .control_plane import (
    AuthorityDecision,
    AuthorityDecisionAction,
    ExecutionClassification,
    GovernanceProposal,
    GovernanceValidation,
    LifecycleEvent,
    LifecycleTransition,
    ProposalOrigin,
)
from .impact import ImpactProjection, SemanticDiff
from .snapshots import ExecutionFingerprint, GovernanceSnapshot
from .sources import SourceObservation, SourceVerification


class EvolutionLedgerError(ValueError):
    """Raised when evolution history is incomplete, inconsistent, or altered."""


class LedgerIntegrityError(EvolutionLedgerError):
    """Raised when a sealed entry or its hash-chain position cannot be verified."""


GENESIS_LEDGER_ENTRY_ID = "GOVERNED-EVOLUTION-LEDGER-GENESIS"


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise EvolutionLedgerError(f"{field_name} must be a non-empty exact identity")
    return value


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field_name)


def _typed_tuple(
    values: Iterable[Any],
    expected_type: type[Any],
    field_name: str,
    identity_attribute: str,
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise EvolutionLedgerError(f"{field_name} must be a collection")
    try:
        collected = tuple(values)
    except TypeError as exc:
        raise EvolutionLedgerError(f"{field_name} must be a collection") from exc
    if any(not isinstance(item, expected_type) for item in collected):
        raise EvolutionLedgerError(
            f"{field_name} must contain {expected_type.__name__} values"
        )
    identities = [getattr(item, identity_attribute) for item in collected]
    if len(identities) != len(set(identities)):
        raise EvolutionLedgerError(f"{field_name} contains duplicate identities")
    return tuple(sorted(collected, key=lambda item: getattr(item, identity_attribute)))


class IdentityAvailability(str, Enum):
    """Whether a reproduction component has an exact machine identity."""

    EXACT = "EXACT_IDENTITY"
    UNKNOWN = "UNKNOWN"
    NOT_MEASURED = "NOT_MEASURED"


class ReproductionComponent(str, Enum):
    FACTORY_SOURCE = "FACTORY_SOURCE_IDENTITY"
    REQUIREMENT = "REQUIREMENT_IDENTITY"
    GOVERNANCE_SNAPSHOT = "GOVERNANCE_SNAPSHOT_IDENTITY"
    EVIDENCE_SNAPSHOT = "EVIDENCE_SNAPSHOT_IDENTITY"
    TOOL_CONFIG = "TOOL_CONFIG_IDENTITY"
    EXECUTION_FINGERPRINT = "EXECUTION_FINGERPRINT_IDENTITY"


@dataclass(frozen=True)
class ReproductionIdentity:
    """One exact identity or an explicit absence classification."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.reproduction-identity.v1"

    component: ReproductionComponent
    availability: IdentityAvailability
    identity: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.component, ReproductionComponent):
            raise EvolutionLedgerError("component must use ReproductionComponent")
        if not isinstance(self.availability, IdentityAvailability):
            raise EvolutionLedgerError("availability must use IdentityAvailability")
        if self.availability is IdentityAvailability.EXACT:
            _identifier(self.identity, "identity")
        elif self.identity is not None:
            raise EvolutionLedgerError(
                "UNKNOWN or NOT_MEASURED reproduction facts cannot contain an identity"
            )

    @classmethod
    def exact(
        cls, component: ReproductionComponent, identity: str
    ) -> ReproductionIdentity:
        return cls(component, IdentityAvailability.EXACT, identity)

    @classmethod
    def unavailable(
        cls,
        component: ReproductionComponent,
        availability: IdentityAvailability,
    ) -> ReproductionIdentity:
        if availability is IdentityAvailability.EXACT:
            raise EvolutionLedgerError("unavailable identity status cannot be EXACT")
        return cls(component, availability, None)

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    def to_dict(self) -> dict[str, str | None]:
        return {
            "availability": self.availability.value,
            "component": self.component.value,
            "identity": self.identity,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ReproductionRecord:
    """Versioned exact inputs needed to reproduce an execution decision.

    A record can retain partial historical knowledge, but it is runnable only
    when it embeds an :class:`ExecutionFingerprint` and every component agrees
    with that fingerprint.  Missing facts use typed statuses, never timestamps
    or narrative placeholders.
    """

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.evolution-reproduction-record.v1"

    identities: tuple[ReproductionIdentity, ...]
    execution_fingerprint: ExecutionFingerprint | None = None
    _reproduction_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        identities = _typed_tuple(
            self.identities,
            ReproductionIdentity,
            "identities",
            "component",
        )
        by_component = {item.component: item for item in identities}
        expected = set(ReproductionComponent)
        if set(by_component) != expected:
            missing = sorted(item.value for item in expected - set(by_component))
            extra = sorted(item.value for item in set(by_component) - expected)
            raise EvolutionLedgerError(
                f"reproduction identities must cover every component; missing={missing}, "
                f"extra={extra}"
            )
        identities = tuple(sorted(identities, key=lambda item: item.component.value))
        object.__setattr__(self, "identities", identities)

        if self.execution_fingerprint is not None:
            if not isinstance(self.execution_fingerprint, ExecutionFingerprint):
                raise EvolutionLedgerError(
                    "execution_fingerprint must be an ExecutionFingerprint"
                )
            expected_identities = {
                ReproductionComponent.FACTORY_SOURCE: (
                    self.execution_fingerprint.factory_source_identity
                ),
                ReproductionComponent.REQUIREMENT: (
                    self.execution_fingerprint.requirement_identity
                ),
                ReproductionComponent.GOVERNANCE_SNAPSHOT: (
                    self.execution_fingerprint.governance_snapshot_identity
                ),
                ReproductionComponent.EVIDENCE_SNAPSHOT: (
                    self.execution_fingerprint.evidence_snapshot_identity
                ),
                ReproductionComponent.TOOL_CONFIG: (
                    self.execution_fingerprint.tool_config_identity
                ),
                ReproductionComponent.EXECUTION_FINGERPRINT: (
                    self.execution_fingerprint.fingerprint_id
                ),
            }
            for component, expected_identity in expected_identities.items():
                fact = by_component[component]
                if (
                    fact.availability is not IdentityAvailability.EXACT
                    or fact.identity != expected_identity
                ):
                    raise EvolutionLedgerError(
                        "reproduction identity does not match the execution fingerprint: "
                        f"{component.value}"
                    )

        object.__setattr__(
            self,
            "_reproduction_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @classmethod
    def from_execution_fingerprint(
        cls, fingerprint: ExecutionFingerprint
    ) -> ReproductionRecord:
        if not isinstance(fingerprint, ExecutionFingerprint):
            raise EvolutionLedgerError("fingerprint must be an ExecutionFingerprint")
        exact = (
            (ReproductionComponent.FACTORY_SOURCE, fingerprint.factory_source_identity),
            (ReproductionComponent.REQUIREMENT, fingerprint.requirement_identity),
            (
                ReproductionComponent.GOVERNANCE_SNAPSHOT,
                fingerprint.governance_snapshot_identity,
            ),
            (
                ReproductionComponent.EVIDENCE_SNAPSHOT,
                fingerprint.evidence_snapshot_identity,
            ),
            (ReproductionComponent.TOOL_CONFIG, fingerprint.tool_config_identity),
            (ReproductionComponent.EXECUTION_FINGERPRINT, fingerprint.fingerprint_id),
        )
        return cls(
            identities=tuple(
                ReproductionIdentity.exact(component, identity)
                for component, identity in exact
            ),
            execution_fingerprint=fingerprint,
        )

    @classmethod
    def non_runnable(
        cls,
        governance_snapshot_identity: str,
        *,
        unavailable: IdentityAvailability = IdentityAvailability.UNKNOWN,
        available_identities: Mapping[ReproductionComponent, str] | None = None,
    ) -> ReproductionRecord:
        """Create an explicit partial record without inventing missing inputs."""
        _identifier(governance_snapshot_identity, "governance_snapshot_identity")
        if unavailable is IdentityAvailability.EXACT:
            raise EvolutionLedgerError("unavailable status must be UNKNOWN or NOT_MEASURED")
        supplied = dict(available_identities or {})
        supplied[ReproductionComponent.GOVERNANCE_SNAPSHOT] = (
            governance_snapshot_identity
        )
        if any(not isinstance(key, ReproductionComponent) for key in supplied):
            raise EvolutionLedgerError(
                "available_identities keys must use ReproductionComponent"
            )
        identities = tuple(
            ReproductionIdentity.exact(component, supplied[component])
            if component in supplied
            else ReproductionIdentity.unavailable(component, unavailable)
            for component in ReproductionComponent
        )
        return cls(identities=identities)

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def is_runnable(self) -> bool:
        return self.execution_fingerprint is not None and all(
            item.availability is IdentityAvailability.EXACT for item in self.identities
        )

    @property
    def unavailable_components(self) -> tuple[ReproductionComponent, ...]:
        return tuple(
            item.component
            for item in self.identities
            if item.availability is not IdentityAvailability.EXACT
        )

    def fact(self, component: ReproductionComponent) -> ReproductionIdentity:
        if not isinstance(component, ReproductionComponent):
            raise EvolutionLedgerError("component must use ReproductionComponent")
        return next(item for item in self.identities if item.component is component)

    def identity_for(self, component: ReproductionComponent) -> str | None:
        return self.fact(component).identity

    @property
    def reproduction_sha256(self) -> str:
        return self._reproduction_sha256

    @property
    def identity_sha256(self) -> str:
        return self.reproduction_sha256

    @property
    def reproduction_id(self) -> str:
        return f"EVOLUTION-REPRODUCTION-{self.reproduction_sha256}"

    @property
    def replay_identity(self) -> str:
        return self.reproduction_id

    def identity_payload(self) -> dict[str, Any]:
        return {
            "execution_fingerprint": (
                self.execution_fingerprint.to_dict()
                if self.execution_fingerprint is not None
                else None
            ),
            "identities": [item.to_dict() for item in self.identities],
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "is_runnable": self.is_runnable,
            "reproduction_id": self.reproduction_id,
            "reproduction_sha256": self.reproduction_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


class MeasurementStatus(str, Enum):
    """Whether an affected-execution policy was actually derived."""

    MEASURED = "MEASURED"
    UNKNOWN = "UNKNOWN"
    NOT_MEASURED = "NOT_MEASURED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class AffectedExecutionPolicy:
    """Exact classifications or an explicit reason that none are asserted."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.affected-execution-policy.v1"

    target_snapshot_id: str
    authority_decision_id: str
    measurement_status: MeasurementStatus
    classifications: tuple[ExecutionClassification, ...] = ()
    _policy_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _identifier(self.target_snapshot_id, "target_snapshot_id")
        _identifier(self.authority_decision_id, "authority_decision_id")
        if not isinstance(self.measurement_status, MeasurementStatus):
            raise EvolutionLedgerError("measurement_status must use MeasurementStatus")
        classifications = _typed_tuple(
            self.classifications,
            ExecutionClassification,
            "classifications",
            "execution_id",
        )
        object.__setattr__(self, "classifications", classifications)
        if self.measurement_status is not MeasurementStatus.MEASURED and classifications:
            raise EvolutionLedgerError(
                "unmeasured execution policy cannot assert classifications"
            )
        for item in classifications:
            if item.governance_snapshot_id != self.target_snapshot_id:
                raise EvolutionLedgerError(
                    "execution classification targets a different snapshot"
                )
            if (
                item.authority_decision_id is not None
                and item.authority_decision_id != self.authority_decision_id
            ):
                raise EvolutionLedgerError(
                    "execution classification targets a different authority decision"
                )
        object.__setattr__(
            self, "_policy_sha256", canonical_sha256(self.identity_payload())
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def policy_sha256(self) -> str:
        return self._policy_sha256

    @property
    def identity_sha256(self) -> str:
        return self.policy_sha256

    @property
    def policy_id(self) -> str:
        return f"AFFECTED-EXECUTION-POLICY-{self.policy_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_decision_id": self.authority_decision_id,
            "classifications": [item.to_dict() for item in self.classifications],
            "measurement_status": self.measurement_status.value,
            "schema_version": self.schema_version,
            "target_snapshot_id": self.target_snapshot_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "policy_id": self.policy_id,
            "policy_sha256": self.policy_sha256,
        }


class EvidenceAuthorityRole(str, Enum):
    """Authority boundary for evidence bound into an evolution record."""

    OBSERVATION_NON_AUTHORITATIVE = "OBSERVATION_NON_AUTHORITATIVE"
    AI_PROPOSAL_NON_AUTHORITATIVE = "AI_PROPOSAL_NON_AUTHORITATIVE"
    HUMAN_PROPOSAL_NON_AUTHORITATIVE = "HUMAN_PROPOSAL_NON_AUTHORITATIVE"
    TOOL_PROPOSAL_NON_AUTHORITATIVE = "TOOL_PROPOSAL_NON_AUTHORITATIVE"
    SOURCE_FACT_AUTHORITY_VERIFIED = "SOURCE_FACT_AUTHORITY_VERIFIED"
    SOURCE_FACT_UNVERIFIED = "SOURCE_FACT_UNVERIFIED"
    VALIDATION_EVIDENCE_NON_AUTHORITY = "VALIDATION_EVIDENCE_NON_AUTHORITY"
    GOVERNED_AUTHORITY_DECISION = "GOVERNED_AUTHORITY_DECISION"


@dataclass(frozen=True)
class EvidenceAuthorityClassification:
    evidence_identity: str
    role: EvidenceAuthorityRole

    def __post_init__(self) -> None:
        _identifier(self.evidence_identity, "evidence_identity")
        if not isinstance(self.role, EvidenceAuthorityRole):
            raise EvolutionLedgerError("role must use EvidenceAuthorityRole")

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_identity": self.evidence_identity,
            "role": self.role.value,
        }


_EVENT_BY_ACTION: dict[AuthorityDecisionAction, LifecycleEvent] = {
    AuthorityDecisionAction.PROMOTE: LifecycleEvent.PROMOTE,
    AuthorityDecisionAction.REVOKE: LifecycleEvent.REVOKE,
    AuthorityDecisionAction.QUARANTINE: LifecycleEvent.QUARANTINE,
    AuthorityDecisionAction.ROLLBACK: LifecycleEvent.ROLLBACK,
}


@dataclass(frozen=True)
class GovernedEvolutionRecord:
    """All exact evidence for one governed adaptation decision and result."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governed-evolution-record.v1"

    action: AuthorityDecisionAction
    change_reason_evidence_identity: str
    source_observations: tuple[SourceObservation, ...]
    source_verifications: tuple[SourceVerification, ...]
    prior_snapshot: GovernanceSnapshot | None
    semantic_diff: SemanticDiff | None
    impact_projection: ImpactProjection | None
    proposal: GovernanceProposal | None
    validation: GovernanceValidation | None
    authority_decision: AuthorityDecision
    resulting_snapshot: GovernanceSnapshot
    lifecycle_transition: LifecycleTransition
    affected_execution_policy: AffectedExecutionPolicy
    reproduction: ReproductionRecord
    _record_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.action, AuthorityDecisionAction):
            raise EvolutionLedgerError("action must use AuthorityDecisionAction")
        _identifier(
            self.change_reason_evidence_identity,
            "change_reason_evidence_identity",
        )
        observations = _typed_tuple(
            self.source_observations,
            SourceObservation,
            "source_observations",
            "observation_id",
        )
        verifications = _typed_tuple(
            self.source_verifications,
            SourceVerification,
            "source_verifications",
            "verification_id",
        )
        object.__setattr__(self, "source_observations", observations)
        object.__setattr__(self, "source_verifications", verifications)
        self._validate_types()
        self._validate_sources(observations, verifications)
        self._validate_diff_and_impact()
        self._validate_decision_chain()
        self._validate_reproduction()
        object.__setattr__(
            self, "_record_sha256", canonical_sha256(self.identity_payload())
        )

    def _validate_types(self) -> None:
        optional_types: tuple[tuple[object, type[Any], str], ...] = (
            (self.prior_snapshot, GovernanceSnapshot, "prior_snapshot"),
            (self.semantic_diff, SemanticDiff, "semantic_diff"),
            (self.impact_projection, ImpactProjection, "impact_projection"),
            (self.proposal, GovernanceProposal, "proposal"),
            (self.validation, GovernanceValidation, "validation"),
        )
        for value, expected, field_name in optional_types:
            if value is not None and not isinstance(value, expected):
                raise EvolutionLedgerError(f"{field_name} must be {expected.__name__}")
        required_types: tuple[tuple[object, type[Any], str], ...] = (
            (self.authority_decision, AuthorityDecision, "authority_decision"),
            (self.resulting_snapshot, GovernanceSnapshot, "resulting_snapshot"),
            (self.lifecycle_transition, LifecycleTransition, "lifecycle_transition"),
            (
                self.affected_execution_policy,
                AffectedExecutionPolicy,
                "affected_execution_policy",
            ),
            (self.reproduction, ReproductionRecord, "reproduction"),
        )
        for value, expected, field_name in required_types:
            if not isinstance(value, expected):
                raise EvolutionLedgerError(f"{field_name} must be {expected.__name__}")

    def _validate_sources(
        self,
        observations: tuple[SourceObservation, ...],
        verifications: tuple[SourceVerification, ...],
    ) -> None:
        observation_ids = {item.observation_id for item in observations}
        if any(item.observation_id not in observation_ids for item in verifications):
            raise EvolutionLedgerError(
                "every source verification must bind a retained observation"
            )
        if self.action is not AuthorityDecisionAction.PROMOTE:
            return
        if not observations or not verifications:
            raise EvolutionLedgerError(
                "promotion history requires observation and authority verification evidence"
            )
        if any(not item.is_authority_verified for item in verifications):
            raise EvolutionLedgerError(
                "promotion cannot treat unverified source evidence as authority"
            )
        expected_bindings = {
            item.source_id: item.to_dict()
            for item in self.resulting_snapshot.source_bindings
        }
        actual_bindings = {
            item.require_authoritative_binding().source_id: (
                item.require_authoritative_binding().to_dict()
            )
            for item in verifications
        }
        if actual_bindings != expected_bindings:
            raise EvolutionLedgerError(
                "source verifications do not exactly bind the resulting snapshot"
            )

    def _validate_diff_and_impact(self) -> None:
        if self.prior_snapshot is None:
            if self.semantic_diff is not None or self.impact_projection is not None:
                raise EvolutionLedgerError(
                    "semantic diff and impact require an exact prior snapshot"
                )
        else:
            if self.semantic_diff is not None:
                if (
                    self.semantic_diff.before_snapshot_id
                    != self.prior_snapshot.snapshot_id
                    or self.semantic_diff.after_snapshot_id
                    != self.resulting_snapshot.snapshot_id
                ):
                    raise EvolutionLedgerError(
                        "semantic diff does not bind the prior and resulting snapshots"
                    )
            if self.action is AuthorityDecisionAction.PROMOTE:
                if self.semantic_diff is None or self.impact_projection is None:
                    raise EvolutionLedgerError(
                        "successor promotion requires semantic diff and impact evidence"
                    )
                if (
                    self.resulting_snapshot.previous_snapshot_id
                    != self.prior_snapshot.snapshot_id
                    or self.resulting_snapshot.supersedes_snapshot_id
                    != self.prior_snapshot.snapshot_id
                ):
                    raise EvolutionLedgerError(
                        "successor promotion has broken immutable snapshot lineage"
                    )
        if self.impact_projection is not None:
            if self.semantic_diff is None:
                raise EvolutionLedgerError("impact projection requires a semantic diff")
            if self.impact_projection.semantic_diff_id != self.semantic_diff.diff_id:
                raise EvolutionLedgerError(
                    "impact projection targets a different semantic diff"
                )

    def _validate_decision_chain(self) -> None:
        snapshot_id = self.resulting_snapshot.snapshot_id
        if self.authority_decision.action is not self.action:
            raise EvolutionLedgerError("record action differs from authority decision")
        if self.authority_decision.target_snapshot_id != snapshot_id:
            raise EvolutionLedgerError(
                "authority decision targets a different resulting snapshot"
            )
        if self.lifecycle_transition.event is not _EVENT_BY_ACTION[self.action]:
            raise EvolutionLedgerError(
                "lifecycle transition does not match the authority action"
            )
        if self.lifecycle_transition.snapshot_id != snapshot_id:
            raise EvolutionLedgerError(
                "lifecycle transition targets a different resulting snapshot"
            )
        if (
            self.lifecycle_transition.authority_decision_id
            != self.authority_decision.decision_id
            or self.lifecycle_transition.cause_identity
            != self.authority_decision.decision_id
        ):
            raise EvolutionLedgerError(
                "lifecycle transition does not bind the authority decision"
            )
        if self.action is AuthorityDecisionAction.PROMOTE:
            if self.proposal is None or self.validation is None:
                raise EvolutionLedgerError(
                    "promotion history requires proposal and validation identities"
                )
            if self.proposal.target_snapshot_id != snapshot_id:
                raise EvolutionLedgerError("proposal targets a different snapshot")
            if (
                self.validation.target_snapshot_id != snapshot_id
                or self.validation.proposal_id != self.proposal.proposal_id
                or not self.validation.passed
            ):
                raise EvolutionLedgerError(
                    "promotion history requires a passing validation bound to its proposal"
                )
            if (
                self.authority_decision.proposal_id != self.proposal.proposal_id
                or self.authority_decision.validation_id
                != self.validation.validation_id
            ):
                raise EvolutionLedgerError(
                    "authority decision does not bind the proposal and validation"
                )
        elif (self.proposal is None) is not (self.validation is None):
            raise EvolutionLedgerError(
                "non-promotion proposal and validation context must be supplied together"
            )
        elif self.proposal is not None and self.validation is not None:
            if (
                self.proposal.target_snapshot_id != snapshot_id
                or self.validation.target_snapshot_id != snapshot_id
                or self.validation.proposal_id != self.proposal.proposal_id
            ):
                raise EvolutionLedgerError(
                    "retained proposal/validation context targets another snapshot"
                )

        if (
            self.affected_execution_policy.target_snapshot_id != snapshot_id
            or self.affected_execution_policy.authority_decision_id
            != self.authority_decision.decision_id
        ):
            raise EvolutionLedgerError(
                "affected execution policy does not bind the decision result"
            )

    def _validate_reproduction(self) -> None:
        governed = self.reproduction.fact(
            ReproductionComponent.GOVERNANCE_SNAPSHOT
        )
        if (
            governed.availability is not IdentityAvailability.EXACT
            or governed.identity != self.resulting_snapshot.snapshot_id
        ):
            raise EvolutionLedgerError(
                "reproduction record must exactly identify the resulting snapshot"
            )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def evidence_authority(self) -> tuple[EvidenceAuthorityClassification, ...]:
        classified: list[EvidenceAuthorityClassification] = [
            EvidenceAuthorityClassification(
                item.observation_id,
                EvidenceAuthorityRole.OBSERVATION_NON_AUTHORITATIVE,
            )
            for item in self.source_observations
        ]
        classified.extend(
            EvidenceAuthorityClassification(
                item.verification_id,
                (
                    EvidenceAuthorityRole.SOURCE_FACT_AUTHORITY_VERIFIED
                    if item.is_authority_verified
                    else EvidenceAuthorityRole.SOURCE_FACT_UNVERIFIED
                ),
            )
            for item in self.source_verifications
        )
        if self.proposal is not None:
            proposal_roles = {
                ProposalOrigin.AI: EvidenceAuthorityRole.AI_PROPOSAL_NON_AUTHORITATIVE,
                ProposalOrigin.HUMAN: (
                    EvidenceAuthorityRole.HUMAN_PROPOSAL_NON_AUTHORITATIVE
                ),
                ProposalOrigin.DETERMINISTIC_TOOL: (
                    EvidenceAuthorityRole.TOOL_PROPOSAL_NON_AUTHORITATIVE
                ),
            }
            classified.append(
                EvidenceAuthorityClassification(
                    self.proposal.proposal_id,
                    proposal_roles[self.proposal.origin],
                )
            )
        if self.validation is not None:
            classified.append(
                EvidenceAuthorityClassification(
                    self.validation.validation_id,
                    EvidenceAuthorityRole.VALIDATION_EVIDENCE_NON_AUTHORITY,
                )
            )
        classified.append(
            EvidenceAuthorityClassification(
                self.authority_decision.decision_id,
                EvidenceAuthorityRole.GOVERNED_AUTHORITY_DECISION,
            )
        )
        return tuple(
            sorted(classified, key=lambda item: (item.evidence_identity, item.role.value))
        )

    @property
    def record_sha256(self) -> str:
        return self._record_sha256

    @property
    def identity_sha256(self) -> str:
        return self.record_sha256

    @property
    def record_id(self) -> str:
        return f"GOVERNED-EVOLUTION-RECORD-{self.record_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "affected_execution_policy": self.affected_execution_policy.to_dict(),
            "authority_decision": self.authority_decision.to_dict(),
            "change_reason_evidence_identity": self.change_reason_evidence_identity,
            "evidence_authority": [item.to_dict() for item in self.evidence_authority],
            "impact_projection": (
                self.impact_projection.to_dict()
                if self.impact_projection is not None
                else None
            ),
            "lifecycle_transition": self.lifecycle_transition.to_dict(),
            "prior_snapshot": (
                self.prior_snapshot.to_dict() if self.prior_snapshot is not None else None
            ),
            "proposal": self.proposal.to_dict() if self.proposal is not None else None,
            "reproduction": self.reproduction.to_dict(),
            "resulting_snapshot": self.resulting_snapshot.to_dict(),
            "schema_version": self.schema_version,
            "semantic_diff": (
                self.semantic_diff.to_dict() if self.semantic_diff is not None else None
            ),
            "source_observations": [item.to_dict() for item in self.source_observations],
            "source_verifications": [
                item.to_dict() for item in self.source_verifications
            ],
            "validation": self.validation.to_dict() if self.validation is not None else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "record_id": self.record_id,
            "record_sha256": self.record_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class EvolutionLedgerEntry:
    """One immutable record sealed into a deterministic predecessor chain."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.evolution-ledger-entry.v1"

    sequence: int
    previous_entry_id: str
    record: GovernedEvolutionRecord
    _entry_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise EvolutionLedgerError("sequence must be a positive integer")
        if self.sequence < 1:
            raise EvolutionLedgerError("sequence must be a positive integer")
        _identifier(self.previous_entry_id, "previous_entry_id")
        if not isinstance(self.record, GovernedEvolutionRecord):
            raise EvolutionLedgerError("record must be GovernedEvolutionRecord")
        object.__setattr__(
            self, "_entry_sha256", canonical_sha256(self.identity_payload())
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def entry_sha256(self) -> str:
        return self._entry_sha256

    @property
    def identity_sha256(self) -> str:
        return self.entry_sha256

    @property
    def entry_id(self) -> str:
        return f"GOVERNED-EVOLUTION-LEDGER-ENTRY-{self.entry_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "previous_entry_id": self.previous_entry_id,
            "record": self.record.to_dict(),
            "schema_version": self.schema_version,
            "sequence": self.sequence,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "entry_id": self.entry_id,
            "entry_sha256": self.entry_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def verify_seal(self) -> None:
        if canonical_sha256(self.record.identity_payload()) != self.record.record_sha256:
            raise LedgerIntegrityError("evolution record content does not match its seal")
        if canonical_sha256(self.identity_payload()) != self.entry_sha256:
            raise LedgerIntegrityError("ledger entry content does not match its seal")


@dataclass(frozen=True)
class EvolutionExplanationRecord:
    """Machine-readable explanation made only of exact governed identities."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.evolution-explanation-record.v1"

    ledger_entry_id: str
    action: AuthorityDecisionAction
    change_reason_evidence_identity: str
    observation_ids: tuple[str, ...]
    source_verification_ids: tuple[str, ...]
    prior_snapshot_id: str | None
    semantic_diff_id: str | None
    impact_projection_id: str | None
    proposal_id: str | None
    validation_id: str | None
    authority_decision_id: str
    resulting_snapshot_id: str
    lifecycle_transition_id: str
    affected_execution_policy_id: str
    reproduction: ReproductionRecord
    _explanation_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for field_name in (
            "ledger_entry_id",
            "change_reason_evidence_identity",
            "authority_decision_id",
            "resulting_snapshot_id",
            "lifecycle_transition_id",
            "affected_execution_policy_id",
        ):
            _identifier(getattr(self, field_name), field_name)
        for field_name in (
            "prior_snapshot_id",
            "semantic_diff_id",
            "impact_projection_id",
            "proposal_id",
            "validation_id",
        ):
            _optional_identifier(getattr(self, field_name), field_name)
        if not isinstance(self.action, AuthorityDecisionAction):
            raise EvolutionLedgerError("action must use AuthorityDecisionAction")
        if not isinstance(self.reproduction, ReproductionRecord):
            raise EvolutionLedgerError("reproduction must be ReproductionRecord")
        for field_name in ("observation_ids", "source_verification_ids"):
            values = tuple(getattr(self, field_name))
            for value in values:
                _identifier(value, field_name)
            if len(values) != len(set(values)):
                raise EvolutionLedgerError(f"{field_name} contains duplicate identities")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        object.__setattr__(
            self,
            "_explanation_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @classmethod
    def from_entry(cls, entry: EvolutionLedgerEntry) -> EvolutionExplanationRecord:
        if not isinstance(entry, EvolutionLedgerEntry):
            raise EvolutionLedgerError("entry must be EvolutionLedgerEntry")
        record = entry.record
        return cls(
            ledger_entry_id=entry.entry_id,
            action=record.action,
            change_reason_evidence_identity=record.change_reason_evidence_identity,
            observation_ids=tuple(
                item.observation_id for item in record.source_observations
            ),
            source_verification_ids=tuple(
                item.verification_id for item in record.source_verifications
            ),
            prior_snapshot_id=(
                record.prior_snapshot.snapshot_id
                if record.prior_snapshot is not None
                else None
            ),
            semantic_diff_id=(
                record.semantic_diff.diff_id if record.semantic_diff is not None else None
            ),
            impact_projection_id=(
                record.impact_projection.impact_id
                if record.impact_projection is not None
                else None
            ),
            proposal_id=(record.proposal.proposal_id if record.proposal is not None else None),
            validation_id=(
                record.validation.validation_id if record.validation is not None else None
            ),
            authority_decision_id=record.authority_decision.decision_id,
            resulting_snapshot_id=record.resulting_snapshot.snapshot_id,
            lifecycle_transition_id=record.lifecycle_transition.transition_id,
            affected_execution_policy_id=record.affected_execution_policy.policy_id,
            reproduction=record.reproduction,
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def explanation_sha256(self) -> str:
        return self._explanation_sha256

    @property
    def identity_sha256(self) -> str:
        return self.explanation_sha256

    @property
    def explanation_id(self) -> str:
        return f"EVOLUTION-EXPLANATION-{self.explanation_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "affected_execution_policy_id": self.affected_execution_policy_id,
            "authority_decision_id": self.authority_decision_id,
            "change_reason_evidence_identity": self.change_reason_evidence_identity,
            "impact_projection_id": self.impact_projection_id,
            "ledger_entry_id": self.ledger_entry_id,
            "lifecycle_transition_id": self.lifecycle_transition_id,
            "observation_ids": list(self.observation_ids),
            "prior_snapshot_id": self.prior_snapshot_id,
            "proposal_id": self.proposal_id,
            "reproduction": self.reproduction.to_dict(),
            "resulting_snapshot_id": self.resulting_snapshot_id,
            "schema_version": self.schema_version,
            "semantic_diff_id": self.semantic_diff_id,
            "source_verification_ids": list(self.source_verification_ids),
            "validation_id": self.validation_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "explanation_id": self.explanation_id,
            "explanation_sha256": self.explanation_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


class EvolutionLedger:
    """Append-only coordinator for immutable hash-chained evolution entries."""

    SCHEMA_VERSION = "upi_app_factory.evolution-ledger.v1"

    def __init__(self) -> None:
        self._entries: tuple[EvolutionLedgerEntry, ...] = ()

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def entries(self) -> tuple[EvolutionLedgerEntry, ...]:
        return self._entries

    @property
    def head_entry_id(self) -> str:
        return self._entries[-1].entry_id if self._entries else GENESIS_LEDGER_ENTRY_ID

    def append(self, record: GovernedEvolutionRecord) -> EvolutionLedgerEntry:
        if not isinstance(record, GovernedEvolutionRecord):
            raise EvolutionLedgerError("record must be GovernedEvolutionRecord")
        self.verify_integrity()
        entry = EvolutionLedgerEntry(
            sequence=len(self._entries) + 1,
            previous_entry_id=self.head_entry_id,
            record=record,
        )
        self.append_sealed(entry)
        return entry

    def append_sealed(self, entry: EvolutionLedgerEntry) -> EvolutionLedgerEntry:
        """Replay an existing seal only at its exact predecessor position."""
        if not isinstance(entry, EvolutionLedgerEntry):
            raise EvolutionLedgerError("entry must be EvolutionLedgerEntry")
        self.verify_integrity()
        entry.verify_seal()
        expected_sequence = len(self._entries) + 1
        if entry.sequence != expected_sequence:
            raise LedgerIntegrityError(
                f"ledger append sequence must be {expected_sequence}; got {entry.sequence}"
            )
        if entry.previous_entry_id != self.head_entry_id:
            raise LedgerIntegrityError("ledger entry has a missing or incorrect predecessor")
        if any(item.record.record_id == entry.record.record_id for item in self._entries):
            raise LedgerIntegrityError("evolution record identity is already sealed")
        self._entries = (*self._entries, entry)
        return entry

    @classmethod
    def replay(cls, entries: Iterable[EvolutionLedgerEntry]) -> EvolutionLedger:
        if isinstance(entries, (str, bytes)):
            raise EvolutionLedgerError("entries must be a collection")
        try:
            supplied = tuple(entries)
        except TypeError as exc:
            raise EvolutionLedgerError("entries must be a collection") from exc
        ledger = cls()
        for entry in supplied:
            ledger.append_sealed(entry)
        return ledger

    def verify_integrity(self) -> bool:
        expected_previous = GENESIS_LEDGER_ENTRY_ID
        seen_records: set[str] = set()
        for expected_sequence, entry in enumerate(self._entries, start=1):
            if not isinstance(entry, EvolutionLedgerEntry):
                raise LedgerIntegrityError("ledger contains an unsealed entry type")
            entry.verify_seal()
            if entry.sequence != expected_sequence:
                raise LedgerIntegrityError("ledger entry sequence is not append order")
            if entry.previous_entry_id != expected_previous:
                raise LedgerIntegrityError("ledger entry predecessor chain is broken")
            if entry.record.record_id in seen_records:
                raise LedgerIntegrityError("ledger contains a duplicate evolution record")
            seen_records.add(entry.record.record_id)
            expected_previous = entry.entry_id
        return True

    def entry(self, entry_id: str) -> EvolutionLedgerEntry:
        _identifier(entry_id, "entry_id")
        for entry in self._entries:
            if entry.entry_id == entry_id:
                return entry
        raise EvolutionLedgerError(f"unknown ledger entry identity: {entry_id}")

    def explain(self, entry_id: str) -> EvolutionExplanationRecord:
        self.verify_integrity()
        return EvolutionExplanationRecord.from_entry(self.entry(entry_id))

    def identity_payload(self) -> dict[str, Any]:
        self.verify_integrity()
        return {
            "entries": [entry.to_dict() for entry in self._entries],
            "entry_count": len(self._entries),
            "head_entry_id": self.head_entry_id,
            "schema_version": self.schema_version,
        }

    @property
    def ledger_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def ledger_id(self) -> str:
        return f"GOVERNED-EVOLUTION-LEDGER-{self.ledger_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "ledger_id": self.ledger_id,
            "ledger_sha256": self.ledger_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


_RECORD_IDENTITY_FIELDS = frozenset(
    {
        "action",
        "affected_execution_policy",
        "authority_decision",
        "change_reason_evidence_identity",
        "evidence_authority",
        "impact_projection",
        "lifecycle_transition",
        "prior_snapshot",
        "proposal",
        "reproduction",
        "resulting_snapshot",
        "schema_version",
        "semantic_diff",
        "source_observations",
        "source_verifications",
        "validation",
    }
)
_RECORD_FIELDS = _RECORD_IDENTITY_FIELDS | {"record_id", "record_sha256"}
_ENTRY_IDENTITY_FIELDS = frozenset(
    {"previous_entry_id", "record", "schema_version", "sequence"}
)
_ENTRY_FIELDS = _ENTRY_IDENTITY_FIELDS | {"entry_id", "entry_sha256"}
_LEDGER_IDENTITY_FIELDS = frozenset(
    {"entries", "entry_count", "head_entry_id", "schema_version"}
)
_LEDGER_FIELDS = _LEDGER_IDENTITY_FIELDS | {"ledger_id", "ledger_sha256"}


def _document_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise LedgerIntegrityError(f"{field_name} must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise LedgerIntegrityError(f"{field_name} keys must be strings")
    return dict(value)


def _require_document_fields(
    value: Mapping[str, Any], expected: frozenset[str], field_name: str
) -> None:
    if set(value) != expected:
        raise LedgerIntegrityError(f"{field_name} has unsupported or missing fields")


def _validate_record_references(record: Mapping[str, Any]) -> None:
    """Fail closed on broken cross-object identities in a serialized record."""
    decision = _document_mapping(record["authority_decision"], "authority_decision")
    resulting = _document_mapping(record["resulting_snapshot"], "resulting_snapshot")
    transition = _document_mapping(record["lifecycle_transition"], "lifecycle_transition")
    policy = _document_mapping(
        record["affected_execution_policy"], "affected_execution_policy"
    )
    reproduction = _document_mapping(record["reproduction"], "reproduction")
    action = record["action"]
    snapshot_id = resulting.get("snapshot_id")
    decision_id = decision.get("decision_id")
    if action not in {item.value for item in AuthorityDecisionAction}:
        raise LedgerIntegrityError("serialized evolution action is unsupported")
    if decision.get("action") != action or decision.get("target_snapshot_id") != snapshot_id:
        raise LedgerIntegrityError("serialized authority decision reference is broken")
    if (
        transition.get("event") != action
        or transition.get("snapshot_id") != snapshot_id
        or transition.get("authority_decision_id") != decision_id
        or transition.get("cause_identity") != decision_id
    ):
        raise LedgerIntegrityError("serialized lifecycle transition reference is broken")
    if (
        policy.get("target_snapshot_id") != snapshot_id
        or policy.get("authority_decision_id") != decision_id
    ):
        raise LedgerIntegrityError("serialized affected execution policy reference is broken")

    identities = reproduction.get("identities")
    if not isinstance(identities, list):
        raise LedgerIntegrityError("serialized reproduction identities must be a list")
    governance_facts = [
        _document_mapping(item, "reproduction identity")
        for item in identities
        if isinstance(item, Mapping)
        and item.get("component")
        == ReproductionComponent.GOVERNANCE_SNAPSHOT.value
    ]
    if len(governance_facts) != 1 or (
        governance_facts[0].get("availability") != IdentityAvailability.EXACT.value
        or governance_facts[0].get("identity") != snapshot_id
    ):
        raise LedgerIntegrityError("serialized reproduction snapshot reference is broken")

    prior = record["prior_snapshot"]
    semantic_diff = record["semantic_diff"]
    impact = record["impact_projection"]
    if prior is None:
        if semantic_diff is not None or impact is not None:
            raise LedgerIntegrityError("serialized diff lacks an exact prior snapshot")
    elif semantic_diff is not None:
        prior_mapping = _document_mapping(prior, "prior_snapshot")
        diff_mapping = _document_mapping(semantic_diff, "semantic_diff")
        if (
            diff_mapping.get("before_snapshot_id") != prior_mapping.get("snapshot_id")
            or diff_mapping.get("after_snapshot_id") != snapshot_id
        ):
            raise LedgerIntegrityError("serialized semantic diff references are broken")
        if impact is not None:
            impact_mapping = _document_mapping(impact, "impact_projection")
            if impact_mapping.get("semantic_diff_id") != diff_mapping.get("diff_id"):
                raise LedgerIntegrityError("serialized impact reference is broken")
    elif impact is not None:
        raise LedgerIntegrityError("serialized impact lacks a semantic diff")

    proposal = record["proposal"]
    validation = record["validation"]
    if action == AuthorityDecisionAction.PROMOTE.value:
        proposal_mapping = _document_mapping(proposal, "proposal")
        validation_mapping = _document_mapping(validation, "validation")
        if (
            proposal_mapping.get("target_snapshot_id") != snapshot_id
            or validation_mapping.get("target_snapshot_id") != snapshot_id
            or validation_mapping.get("proposal_id") != proposal_mapping.get("proposal_id")
            or validation_mapping.get("passed") is not True
            or decision.get("proposal_id") != proposal_mapping.get("proposal_id")
            or decision.get("validation_id") != validation_mapping.get("validation_id")
        ):
            raise LedgerIntegrityError("serialized promotion qualification is broken")


def validate_evolution_ledger_document(
    document: Mapping[str, Any] | str,
) -> dict[str, Any]:
    """Verify canonical JSON, seals, chain order, and exact record references.

    The ledger head identity is the value an external governed artifact must pin.
    Rehashing an altered document produces a different ledger identity and cannot
    preserve that external anchor.
    """
    if isinstance(document, str):
        try:
            decoded = json.loads(document)
        except json.JSONDecodeError as exc:
            raise LedgerIntegrityError("ledger document must be valid JSON") from exc
        if canonical_json(decoded) != document:
            raise LedgerIntegrityError("ledger document must use exact canonical JSON")
    elif isinstance(document, Mapping):
        decoded = json.loads(canonical_json(dict(document)))
    else:
        raise LedgerIntegrityError("ledger document must be canonical JSON or a mapping")

    ledger = _document_mapping(decoded, "ledger document")
    _require_document_fields(ledger, _LEDGER_FIELDS, "ledger document")
    if ledger.get("schema_version") != EvolutionLedger.SCHEMA_VERSION:
        raise LedgerIntegrityError("unsupported ledger schema version")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise LedgerIntegrityError("ledger entries must be a list")
    if ledger.get("entry_count") != len(entries):
        raise LedgerIntegrityError("ledger entry count is inconsistent")

    expected_previous = GENESIS_LEDGER_ENTRY_ID
    seen_records: set[str] = set()
    for expected_sequence, raw_entry in enumerate(entries, start=1):
        entry = _document_mapping(raw_entry, "ledger entry")
        _require_document_fields(entry, _ENTRY_FIELDS, "ledger entry")
        if entry.get("schema_version") != EvolutionLedgerEntry.SCHEMA_VERSION:
            raise LedgerIntegrityError("unsupported ledger entry schema version")
        if entry.get("sequence") != expected_sequence:
            raise LedgerIntegrityError("ledger entry sequence is not append order")
        if entry.get("previous_entry_id") != expected_previous:
            raise LedgerIntegrityError("ledger entry predecessor chain is broken")

        record = _document_mapping(entry.get("record"), "evolution record")
        _require_document_fields(record, _RECORD_FIELDS, "evolution record")
        if record.get("schema_version") != GovernedEvolutionRecord.SCHEMA_VERSION:
            raise LedgerIntegrityError("unsupported evolution record schema version")
        _validate_record_references(record)
        record_payload = {key: record[key] for key in _RECORD_IDENTITY_FIELDS}
        record_sha256 = canonical_sha256(record_payload)
        if (
            record.get("record_sha256") != record_sha256
            or record.get("record_id")
            != f"GOVERNED-EVOLUTION-RECORD-{record_sha256}"
        ):
            raise LedgerIntegrityError("evolution record content does not match its seal")
        record_id = record["record_id"]
        if record_id in seen_records:
            raise LedgerIntegrityError("ledger contains a duplicate evolution record")
        seen_records.add(record_id)

        entry_payload = {key: entry[key] for key in _ENTRY_IDENTITY_FIELDS}
        entry_sha256 = canonical_sha256(entry_payload)
        if (
            entry.get("entry_sha256") != entry_sha256
            or entry.get("entry_id")
            != f"GOVERNED-EVOLUTION-LEDGER-ENTRY-{entry_sha256}"
        ):
            raise LedgerIntegrityError("ledger entry content does not match its seal")
        expected_previous = entry["entry_id"]

    if ledger.get("head_entry_id") != expected_previous:
        raise LedgerIntegrityError("ledger head does not match its predecessor chain")
    ledger_payload = {key: ledger[key] for key in _LEDGER_IDENTITY_FIELDS}
    ledger_sha256 = canonical_sha256(ledger_payload)
    if (
        ledger.get("ledger_sha256") != ledger_sha256
        or ledger.get("ledger_id") != f"GOVERNED-EVOLUTION-LEDGER-{ledger_sha256}"
    ):
        raise LedgerIntegrityError("ledger document content does not match its seal")
    return ledger


# Concise aliases retain a single implementation and identity contract.
GovernanceEvolutionLedger = EvolutionLedger
LedgerEntry = EvolutionLedgerEntry
EvolutionRecord = GovernedEvolutionRecord
ExplanationRecord = EvolutionExplanationRecord
validate_ledger_document = validate_evolution_ledger_document
