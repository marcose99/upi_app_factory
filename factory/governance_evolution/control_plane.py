"""Governed lifecycle control plane and immutable execution pins.

This module extends the M2.4/M2.5 canonical identity and authority-verification
contracts.  It deliberately has no clock or network dependency: callers
supply immutable snapshots, registry-created verification evidence, explicit
qualification records, and authority decisions.  The control plane orders and
checks those inputs; it never infers authority from proposal text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Iterable

from factory.documentation import canonical_json, canonical_sha256

from .snapshots import ExecutionFingerprint, GovernanceSnapshot
from .sources import (
    AuthorityRegistry,
    GovernanceLifecycleState,
    SourceVerification,
)


class ControlPlaneError(ValueError):
    """Raised when a governed lifecycle operation cannot be proved safe."""


class InvalidLifecycleTransition(ControlPlaneError):
    """Raised when a snapshot transition is not in the closed lifecycle."""


class UnauthorizedGovernanceDecision(ControlPlaneError):
    """Raised when a decision is missing, stale, or outside configured authority."""


class ExecutionPinError(ControlPlaneError):
    """Raised when immutable execution pinning cannot be established."""


NO_ACTIVE_SNAPSHOT_ID = "NO-ACTIVE-GOVERNANCE-SNAPSHOT"
GENESIS_TRANSITION_ID = "GOVERNANCE-TRANSITION-GENESIS"


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ControlPlaneError(f"{field_name} must be a non-empty stable identifier")
    return value


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field_name)


def _identity_collection(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ControlPlaneError(f"{field_name} must be a collection")
    try:
        collected = tuple(values)
    except TypeError as exc:
        raise ControlPlaneError(f"{field_name} must be a collection") from exc
    for value in collected:
        _identifier(value, field_name)
    if len(collected) != len(set(collected)):
        raise ControlPlaneError(f"{field_name} must not contain duplicate identities")
    return tuple(sorted(collected))


class ProposalOrigin(str, Enum):
    """Descriptive origin of a proposal; no value in this enum grants authority."""

    AI = "AI_NON_AUTHORITATIVE"
    HUMAN = "HUMAN_PROPOSAL"
    DETERMINISTIC_TOOL = "DETERMINISTIC_TOOL"


class AuthorityDecisionAction(str, Enum):
    PROMOTE = "PROMOTE"
    REVOKE = "REVOKE"
    QUARANTINE = "QUARANTINE"
    ROLLBACK = "ROLLBACK"


class ExecutionDisposition(str, Enum):
    """Deterministic treatment of an execution whose pinned policy is affected."""

    CONTINUE = "CONTINUE"
    QUARANTINE = "QUARANTINE"
    RESTART_REQUIRED = "RESTART_REQUIRED"


class LifecycleEvent(str, Enum):
    OBSERVE = "OBSERVE"
    VERIFY_AUTHORITY = "VERIFY_AUTHORITY"
    PROPOSE = "PROPOSE"
    VALIDATE = "VALIDATE"
    QUALIFICATION_FAILED = "QUALIFICATION_FAILED"
    PROMOTE = "PROMOTE"
    SUPERSEDE = "SUPERSEDE"
    REVOKE = "REVOKE"
    QUARANTINE = "QUARANTINE"
    ROLLBACK = "ROLLBACK"


@dataclass(frozen=True)
class GovernanceProposal:
    """Immutable, explicitly non-authoritative adaptation proposal."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-proposal.v1"

    proposal_id: str
    target_snapshot_id: str
    evidence_identity: str
    proposer_identity: str
    origin: ProposalOrigin
    _proposal_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for field_name in (
            "proposal_id",
            "target_snapshot_id",
            "evidence_identity",
            "proposer_identity",
        ):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.origin, ProposalOrigin):
            raise ControlPlaneError("origin must use ProposalOrigin")
        object.__setattr__(
            self, "_proposal_sha256", canonical_sha256(self.identity_payload())
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def proposal_sha256(self) -> str:
        return self._proposal_sha256

    @property
    def identity_sha256(self) -> str:
        return self.proposal_sha256

    def identity_payload(self) -> dict[str, str]:
        return {
            "evidence_identity": self.evidence_identity,
            "origin": self.origin.value,
            "proposal_id": self.proposal_id,
            "proposer_identity": self.proposer_identity,
            "schema_version": self.schema_version,
            "target_snapshot_id": self.target_snapshot_id,
        }

    def to_dict(self) -> dict[str, str]:
        return {**self.identity_payload(), "proposal_sha256": self.proposal_sha256}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class GovernanceValidation:
    """Deterministic qualification result bound to one proposal and snapshot."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-validation.v1"

    validation_id: str
    target_snapshot_id: str
    proposal_id: str
    evidence_identity: str
    validator_identity: str
    passed: bool
    _validation_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for field_name in (
            "validation_id",
            "target_snapshot_id",
            "proposal_id",
            "evidence_identity",
            "validator_identity",
        ):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.passed, bool):
            raise ControlPlaneError("passed must be an explicit boolean")
        object.__setattr__(
            self, "_validation_sha256", canonical_sha256(self.identity_payload())
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def validation_sha256(self) -> str:
        return self._validation_sha256

    @property
    def identity_sha256(self) -> str:
        return self.validation_sha256

    def identity_payload(self) -> dict[str, Any]:
        return {
            "evidence_identity": self.evidence_identity,
            "passed": self.passed,
            "proposal_id": self.proposal_id,
            "schema_version": self.schema_version,
            "target_snapshot_id": self.target_snapshot_id,
            "validation_id": self.validation_id,
            "validator_identity": self.validator_identity,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "validation_sha256": self.validation_sha256}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class AuthorityDecision:
    """Caller-supplied governed authority record, never synthesized by the plane.

    ``expected_active_snapshot_id`` is an optimistic state guard.  A caller must
    use :data:`NO_ACTIVE_SNAPSHOT_ID` when no active snapshot is expected.  It
    prevents a once-valid decision from being replayed against changed active
    state.
    """

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-authority-decision.v1"

    decision_id: str
    authority_id: str
    action: AuthorityDecisionAction
    target_snapshot_id: str
    evidence_identity: str
    expected_active_snapshot_id: str
    proposal_id: str | None = None
    validation_id: str | None = None
    execution_disposition: ExecutionDisposition | None = None
    _decision_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for field_name in (
            "decision_id",
            "authority_id",
            "target_snapshot_id",
            "evidence_identity",
            "expected_active_snapshot_id",
        ):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.action, AuthorityDecisionAction):
            raise ControlPlaneError("action must use AuthorityDecisionAction")
        _optional_identifier(self.proposal_id, "proposal_id")
        _optional_identifier(self.validation_id, "validation_id")
        if self.execution_disposition is not None and not isinstance(
            self.execution_disposition, ExecutionDisposition
        ):
            raise ControlPlaneError(
                "execution_disposition must use ExecutionDisposition"
            )

        if self.action is AuthorityDecisionAction.PROMOTE:
            if self.proposal_id is None or self.validation_id is None:
                raise ControlPlaneError(
                    "PROMOTE decisions require proposal_id and validation_id"
                )
            if self.execution_disposition is not None:
                raise ControlPlaneError(
                    "PROMOTE decisions cannot assert an execution disposition"
                )
        elif self.action is AuthorityDecisionAction.REVOKE:
            if self.execution_disposition is None:
                raise ControlPlaneError(
                    "REVOKE decisions require an execution disposition"
                )
            if self.proposal_id is not None or self.validation_id is not None:
                raise ControlPlaneError(
                    "REVOKE decisions cannot carry promotion qualification identities"
                )
        elif self.action is AuthorityDecisionAction.QUARANTINE:
            if self.execution_disposition is not ExecutionDisposition.QUARANTINE:
                raise ControlPlaneError(
                    "QUARANTINE decisions require the QUARANTINE execution disposition"
                )
            if self.proposal_id is not None or self.validation_id is not None:
                raise ControlPlaneError(
                    "QUARANTINE decisions cannot carry promotion qualification identities"
                )
        else:
            if self.execution_disposition is not None:
                raise ControlPlaneError(
                    "ROLLBACK decisions cannot assert an execution disposition"
                )
            if self.proposal_id is not None or self.validation_id is not None:
                raise ControlPlaneError(
                    "ROLLBACK decisions cannot carry promotion qualification identities"
                )

        object.__setattr__(
            self, "_decision_sha256", canonical_sha256(self.identity_payload())
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def decision_sha256(self) -> str:
        return self._decision_sha256

    @property
    def identity_sha256(self) -> str:
        return self.decision_sha256

    @property
    def authority_decision_identity(self) -> str:
        return self.decision_id

    @property
    def decision_record_id(self) -> str:
        return f"GOVERNANCE-AUTHORITY-DECISION-{self.decision_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "authority_id": self.authority_id,
            "decision_id": self.decision_id,
            "evidence_identity": self.evidence_identity,
            "execution_disposition": (
                self.execution_disposition.value
                if self.execution_disposition is not None
                else None
            ),
            "expected_active_snapshot_id": self.expected_active_snapshot_id,
            "proposal_id": self.proposal_id,
            "schema_version": self.schema_version,
            "target_snapshot_id": self.target_snapshot_id,
            "validation_id": self.validation_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "decision_record_id": self.decision_record_id,
            "decision_sha256": self.decision_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class LifecycleTransition:
    """One immutable event in the append-only in-memory transition history."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-transition.v1"

    sequence: int
    snapshot_id: str
    from_state: GovernanceLifecycleState | None
    to_state: GovernanceLifecycleState
    event: LifecycleEvent
    cause_identity: str
    authority_decision_id: str | None
    previous_transition_id: str
    _transition_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise ControlPlaneError("sequence must be a positive integer")
        if self.sequence < 1:
            raise ControlPlaneError("sequence must be a positive integer")
        _identifier(self.snapshot_id, "snapshot_id")
        _identifier(self.cause_identity, "cause_identity")
        _optional_identifier(self.authority_decision_id, "authority_decision_id")
        _identifier(self.previous_transition_id, "previous_transition_id")
        if self.from_state is not None and not isinstance(
            self.from_state, GovernanceLifecycleState
        ):
            raise ControlPlaneError("from_state must use GovernanceLifecycleState")
        if not isinstance(self.to_state, GovernanceLifecycleState):
            raise ControlPlaneError("to_state must use GovernanceLifecycleState")
        if not isinstance(self.event, LifecycleEvent):
            raise ControlPlaneError("event must use LifecycleEvent")
        object.__setattr__(
            self, "_transition_sha256", canonical_sha256(self.identity_payload())
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def transition_sha256(self) -> str:
        return self._transition_sha256

    @property
    def identity_sha256(self) -> str:
        return self.transition_sha256

    @property
    def transition_id(self) -> str:
        return f"GOVERNANCE-TRANSITION-{self.transition_sha256}"

    @property
    def state(self) -> GovernanceLifecycleState:
        return self.to_state

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_decision_id": self.authority_decision_id,
            "cause_identity": self.cause_identity,
            "event": self.event.value,
            "from_state": self.from_state.value if self.from_state is not None else None,
            "previous_transition_id": self.previous_transition_id,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "snapshot_id": self.snapshot_id,
            "to_state": self.to_state.value,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "transition_id": self.transition_id,
            "transition_sha256": self.transition_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class ExecutionPin:
    """Immutable binding from one execution identity to one active snapshot."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-execution-pin.v1"

    execution_id: str
    governance_snapshot_id: str
    governance_snapshot_sha256: str
    execution_fingerprint: ExecutionFingerprint
    activation_transition_id: str
    _pin_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _identifier(self.execution_id, "execution_id")
        _identifier(self.governance_snapshot_id, "governance_snapshot_id")
        _identifier(self.governance_snapshot_sha256, "governance_snapshot_sha256")
        _identifier(self.activation_transition_id, "activation_transition_id")
        if not isinstance(self.execution_fingerprint, ExecutionFingerprint):
            raise ExecutionPinError(
                "execution_fingerprint must be an immutable ExecutionFingerprint"
            )
        expected_snapshot_id = (
            f"GOVERNANCE-SNAPSHOT-{self.governance_snapshot_sha256}"
        )
        if self.governance_snapshot_id != expected_snapshot_id:
            raise ExecutionPinError(
                "governance snapshot digest does not match snapshot identity"
            )
        if (
            self.execution_fingerprint.governance_snapshot_identity
            != self.governance_snapshot_id
        ):
            raise ExecutionPinError(
                "execution fingerprint governance identity does not match the pin"
            )
        object.__setattr__(self, "_pin_sha256", canonical_sha256(self.identity_payload()))

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def pin_sha256(self) -> str:
        return self._pin_sha256

    @property
    def identity_sha256(self) -> str:
        return self.pin_sha256

    @property
    def pin_id(self) -> str:
        return f"GOVERNANCE-EXECUTION-PIN-{self.pin_sha256}"

    @property
    def fingerprint(self) -> ExecutionFingerprint:
        return self.execution_fingerprint

    @property
    def snapshot_id(self) -> str:
        return self.governance_snapshot_id

    def identity_payload(self) -> dict[str, str]:
        return {
            "activation_transition_id": self.activation_transition_id,
            "execution_fingerprint_id": self.execution_fingerprint.fingerprint_id,
            "execution_id": self.execution_id,
            "governance_snapshot_id": self.governance_snapshot_id,
            "governance_snapshot_sha256": self.governance_snapshot_sha256,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "execution_fingerprint": self.execution_fingerprint.to_dict(),
            "pin_id": self.pin_id,
            "pin_sha256": self.pin_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class ExecutionClassification:
    """Derived response for a historical execution pin; the pin is never changed."""

    SCHEMA_VERSION: ClassVar[str] = (
        "upi_app_factory.governance-execution-classification.v1"
    )

    execution_id: str
    execution_pin_id: str
    governance_snapshot_id: str
    disposition: ExecutionDisposition
    authority_decision_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.execution_id, "execution_id")
        _identifier(self.execution_pin_id, "execution_pin_id")
        _identifier(self.governance_snapshot_id, "governance_snapshot_id")
        _optional_identifier(self.authority_decision_id, "authority_decision_id")
        if not isinstance(self.disposition, ExecutionDisposition):
            raise ControlPlaneError("disposition must use ExecutionDisposition")

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def classification_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def classification_id(self) -> str:
        return f"EXECUTION-CLASSIFICATION-{self.classification_sha256}"

    def identity_payload(self) -> dict[str, str | None]:
        return {
            "authority_decision_id": self.authority_decision_id,
            "disposition": self.disposition.value,
            "execution_id": self.execution_id,
            "execution_pin_id": self.execution_pin_id,
            "governance_snapshot_id": self.governance_snapshot_id,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, str | None]:
        return {
            **self.identity_payload(),
            "classification_id": self.classification_id,
            "classification_sha256": self.classification_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


_ALLOWED_TRANSITIONS: dict[
    GovernanceLifecycleState | None, frozenset[GovernanceLifecycleState]
] = {
    None: frozenset({GovernanceLifecycleState.OBSERVED_UNVERIFIED}),
    GovernanceLifecycleState.OBSERVED_UNVERIFIED: frozenset(
        {
            GovernanceLifecycleState.AUTHORITY_VERIFIED,
            GovernanceLifecycleState.QUARANTINED,
        }
    ),
    GovernanceLifecycleState.AUTHORITY_VERIFIED: frozenset(
        {
            GovernanceLifecycleState.PROPOSED,
            GovernanceLifecycleState.QUARANTINED,
        }
    ),
    GovernanceLifecycleState.PROPOSED: frozenset(
        {
            GovernanceLifecycleState.VALIDATED,
            GovernanceLifecycleState.QUARANTINED,
        }
    ),
    GovernanceLifecycleState.VALIDATED: frozenset(
        {
            GovernanceLifecycleState.ACTIVE,
            GovernanceLifecycleState.QUARANTINED,
        }
    ),
    GovernanceLifecycleState.ACTIVE: frozenset(
        {
            GovernanceLifecycleState.SUPERSEDED,
            GovernanceLifecycleState.REVOKED,
            GovernanceLifecycleState.QUARANTINED,
        }
    ),
    GovernanceLifecycleState.SUPERSEDED: frozenset(
        {
            GovernanceLifecycleState.ACTIVE,
            GovernanceLifecycleState.REVOKED,
            GovernanceLifecycleState.QUARANTINED,
        }
    ),
    GovernanceLifecycleState.REVOKED: frozenset(),
    GovernanceLifecycleState.QUARANTINED: frozenset(),
}


class GovernanceControlPlane:
    """Repository-local lifecycle coordinator with append-only audit events."""

    SCHEMA_VERSION = "upi_app_factory.governance-control-plane.v1"

    def __init__(
        self,
        authority_registry: AuthorityRegistry | Iterable[AuthorityRegistry],
        decision_authority_ids: Iterable[str],
    ) -> None:
        registries = self._normalize_registries(authority_registry)
        authorities = _identity_collection(
            decision_authority_ids, "decision_authority_ids"
        )
        if not authorities:
            raise ControlPlaneError("decision_authority_ids must not be empty")
        self._registries = {item.registry_id: item for item in registries}
        self._decision_authority_ids = authorities
        self._snapshots: dict[str, GovernanceSnapshot] = {}
        self._version_ids: dict[str, str] = {}
        self._states: dict[str, GovernanceLifecycleState] = {}
        self._transitions: list[LifecycleTransition] = []
        self._verification_ids: dict[str, tuple[str, ...]] = {}
        self._verification_registry_ids: dict[str, str] = {}
        self._proposals: dict[str, GovernanceProposal] = {}
        self._proposal_by_snapshot: dict[str, GovernanceProposal] = {}
        self._validations: dict[str, GovernanceValidation] = {}
        self._validation_by_snapshot: dict[str, GovernanceValidation] = {}
        self._decisions: dict[str, AuthorityDecision] = {}
        self._execution_pins: dict[str, ExecutionPin] = {}
        self._interventions: dict[str, AuthorityDecision] = {}
        self._active_snapshot_id: str | None = None

    @staticmethod
    def _normalize_registries(
        value: AuthorityRegistry | Iterable[AuthorityRegistry],
    ) -> tuple[AuthorityRegistry, ...]:
        registries: tuple[AuthorityRegistry, ...]
        if isinstance(value, AuthorityRegistry):
            registries = (value,)
        else:
            if isinstance(value, (str, bytes)):
                raise ControlPlaneError("authority_registry must be a registry or collection")
            try:
                registries = tuple(value)
            except TypeError as exc:
                raise ControlPlaneError(
                    "authority_registry must be a registry or collection"
                ) from exc
        if not registries or any(
            not isinstance(item, AuthorityRegistry) for item in registries
        ):
            raise ControlPlaneError(
                "authority_registry must contain AuthorityRegistry values"
            )
        registry_ids = [item.registry_id for item in registries]
        if len(registry_ids) != len(set(registry_ids)):
            raise ControlPlaneError("authority_registry contains duplicate identities")
        return tuple(sorted(registries, key=lambda item: item.registry_id))

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def authority_registry_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._registries))

    @property
    def decision_authority_ids(self) -> tuple[str, ...]:
        return self._decision_authority_ids

    @property
    def expected_active_snapshot_id(self) -> str:
        return self._active_snapshot_id or NO_ACTIVE_SNAPSHOT_ID

    @property
    def active_snapshot_id(self) -> str | None:
        return self._active_snapshot_id

    @property
    def active_snapshot(self) -> GovernanceSnapshot | None:
        if self._active_snapshot_id is None:
            return None
        return self._snapshots[self._active_snapshot_id]

    @property
    def transition_history(self) -> tuple[LifecycleTransition, ...]:
        return tuple(self._transitions)

    @property
    def execution_pins(self) -> tuple[ExecutionPin, ...]:
        return tuple(self._execution_pins[key] for key in sorted(self._execution_pins))

    @property
    def snapshot_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._snapshots))

    def snapshot(self, snapshot_id: str) -> GovernanceSnapshot:
        _identifier(snapshot_id, "snapshot_id")
        try:
            return self._snapshots[snapshot_id]
        except KeyError as exc:
            raise ControlPlaneError(f"unknown governance snapshot: {snapshot_id}") from exc

    def snapshot_state(self, snapshot_id: str) -> GovernanceLifecycleState:
        self.snapshot(snapshot_id)
        return self._states[snapshot_id]

    def snapshot_history(self, snapshot_id: str) -> tuple[LifecycleTransition, ...]:
        self.snapshot(snapshot_id)
        return tuple(
            item for item in self._transitions if item.snapshot_id == snapshot_id
        )

    def proposal(self, proposal_id: str) -> GovernanceProposal:
        _identifier(proposal_id, "proposal_id")
        try:
            return self._proposals[proposal_id]
        except KeyError as exc:
            raise ControlPlaneError(f"unknown proposal identity: {proposal_id}") from exc

    def validation(self, validation_id: str) -> GovernanceValidation:
        _identifier(validation_id, "validation_id")
        try:
            return self._validations[validation_id]
        except KeyError as exc:
            raise ControlPlaneError(
                f"unknown validation identity: {validation_id}"
            ) from exc

    def authority_decision(self, decision_id: str) -> AuthorityDecision:
        _identifier(decision_id, "decision_id")
        try:
            return self._decisions[decision_id]
        except KeyError as exc:
            raise ControlPlaneError(
                f"unknown authority decision identity: {decision_id}"
            ) from exc

    def _append_transition(
        self,
        snapshot_id: str,
        to_state: GovernanceLifecycleState,
        event: LifecycleEvent,
        cause_identity: str,
        authority_decision_id: str | None = None,
    ) -> LifecycleTransition:
        from_state = self._states.get(snapshot_id)
        allowed = _ALLOWED_TRANSITIONS.get(from_state, frozenset())
        if to_state not in allowed:
            source = from_state.value if from_state is not None else "UNREGISTERED"
            raise InvalidLifecycleTransition(
                f"invalid governance lifecycle transition: {source} -> {to_state.value}"
            )
        transition = LifecycleTransition(
            sequence=len(self._transitions) + 1,
            snapshot_id=snapshot_id,
            from_state=from_state,
            to_state=to_state,
            event=event,
            cause_identity=cause_identity,
            authority_decision_id=authority_decision_id,
            previous_transition_id=(
                self._transitions[-1].transition_id
                if self._transitions
                else GENESIS_TRANSITION_ID
            ),
        )
        self._transitions.append(transition)
        self._states[snapshot_id] = to_state
        return transition

    def _require_state(
        self, snapshot_id: str, expected: GovernanceLifecycleState
    ) -> None:
        state = self.snapshot_state(snapshot_id)
        if state is not expected:
            raise InvalidLifecycleTransition(
                f"snapshot must be {expected.value}; current state is {state.value}"
            )

    def _check_active_guard(self, decision: AuthorityDecision) -> None:
        if decision.expected_active_snapshot_id != self.expected_active_snapshot_id:
            raise UnauthorizedGovernanceDecision(
                "stale authority decision: expected active snapshot does not match"
            )

    def _check_decision(
        self,
        decision: object,
        *,
        action: AuthorityDecisionAction,
        target_snapshot_id: str,
    ) -> AuthorityDecision:
        if not isinstance(decision, AuthorityDecision):
            raise UnauthorizedGovernanceDecision(
                "an explicit governed AuthorityDecision is required"
            )
        if decision.action is not action:
            raise UnauthorizedGovernanceDecision(
                f"authority decision action must be {action.value}"
            )
        if decision.target_snapshot_id != target_snapshot_id:
            raise UnauthorizedGovernanceDecision(
                "authority decision targets a different governance snapshot"
            )
        if decision.authority_id not in self._decision_authority_ids:
            raise UnauthorizedGovernanceDecision(
                "authority decision identity is not in the configured authority set"
            )
        if decision.decision_id in self._decisions:
            raise UnauthorizedGovernanceDecision(
                "authority decision identity has already been consumed"
            )
        self._check_active_guard(decision)
        return decision

    def _record_decision(self, decision: AuthorityDecision) -> None:
        self._decisions[decision.decision_id] = decision

    def observe_snapshot(self, snapshot: GovernanceSnapshot) -> LifecycleTransition:
        if not isinstance(snapshot, GovernanceSnapshot):
            raise ControlPlaneError(
                "snapshot must be an immutable GovernanceSnapshot"
            )
        if snapshot.snapshot_id in self._snapshots:
            raise ControlPlaneError("governance snapshot identity is already observed")
        if snapshot.version_id in self._version_ids:
            raise ControlPlaneError(
                "governance version_id is already bound to another immutable snapshot"
            )
        self._snapshots[snapshot.snapshot_id] = snapshot
        self._version_ids[snapshot.version_id] = snapshot.snapshot_id
        return self._append_transition(
            snapshot.snapshot_id,
            GovernanceLifecycleState.OBSERVED_UNVERIFIED,
            LifecycleEvent.OBSERVE,
            snapshot.snapshot_id,
        )

    def verify_snapshot(
        self,
        snapshot_id: str,
        verifications: SourceVerification | Iterable[SourceVerification],
    ) -> LifecycleTransition:
        governed = self.snapshot(snapshot_id)
        self._require_state(snapshot_id, GovernanceLifecycleState.OBSERVED_UNVERIFIED)
        supplied: tuple[SourceVerification, ...]
        if isinstance(verifications, SourceVerification):
            supplied = (verifications,)
        else:
            if isinstance(verifications, (str, bytes)):
                raise ControlPlaneError("verifications must be a collection")
            try:
                supplied = tuple(verifications)
            except TypeError as exc:
                raise ControlPlaneError("verifications must be a collection") from exc
        if not supplied or any(
            not isinstance(item, SourceVerification) for item in supplied
        ):
            raise ControlPlaneError(
                "verifications must contain registry-created SourceVerification values"
            )
        verification_ids = [item.verification_id for item in supplied]
        if len(verification_ids) != len(set(verification_ids)):
            raise ControlPlaneError("duplicate source verification identity")
        registry_ids = {item.authority_registry_id for item in supplied}
        if len(registry_ids) != 1:
            raise ControlPlaneError(
                "snapshot verification must use one unambiguous authority registry"
            )
        registry_id = next(iter(registry_ids))
        if registry_id not in self._registries:
            raise ControlPlaneError(
                "source verification uses an unconfigured authority registry"
            )

        verified_bindings = []
        for item in supplied:
            if not item.is_authority_verified:
                raise ControlPlaneError(
                    "stale or unverified source evidence cannot verify a snapshot"
                )
            verified_bindings.append(item.require_authoritative_binding())
        source_ids = [item.source_id for item in verified_bindings]
        if len(source_ids) != len(set(source_ids)):
            raise ControlPlaneError("duplicate verified source identity")
        expected = {
            item.source_id: item.to_dict() for item in governed.source_bindings
        }
        actual = {item.source_id: item.to_dict() for item in verified_bindings}
        if actual != expected:
            raise ControlPlaneError(
                "source verification evidence does not exactly bind the snapshot"
            )

        normalized_ids = tuple(sorted(verification_ids))
        cause_identity = "SNAPSHOT-AUTHORITY-VERIFICATION-" + canonical_sha256(
            {
                "authority_registry_id": registry_id,
                "schema_version": "upi_app_factory.snapshot-authority-verification-set.v1",
                "snapshot_id": snapshot_id,
                "verification_ids": list(normalized_ids),
            }
        )
        self._verification_ids[snapshot_id] = normalized_ids
        self._verification_registry_ids[snapshot_id] = registry_id
        return self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.AUTHORITY_VERIFIED,
            LifecycleEvent.VERIFY_AUTHORITY,
            cause_identity,
        )

    def propose_snapshot(
        self, snapshot_id: str, proposal: GovernanceProposal
    ) -> LifecycleTransition:
        self._require_state(snapshot_id, GovernanceLifecycleState.AUTHORITY_VERIFIED)
        if not isinstance(proposal, GovernanceProposal):
            raise ControlPlaneError("proposal must be GovernanceProposal")
        if proposal.target_snapshot_id != snapshot_id:
            raise ControlPlaneError("proposal targets a different governance snapshot")
        if proposal.proposal_id in self._proposals:
            raise ControlPlaneError("proposal identity is already registered")
        self._proposals[proposal.proposal_id] = proposal
        self._proposal_by_snapshot[snapshot_id] = proposal
        return self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.PROPOSED,
            LifecycleEvent.PROPOSE,
            proposal.proposal_id,
        )

    def validate_snapshot(
        self, snapshot_id: str, validation: GovernanceValidation
    ) -> LifecycleTransition:
        self._require_state(snapshot_id, GovernanceLifecycleState.PROPOSED)
        if not isinstance(validation, GovernanceValidation):
            raise ControlPlaneError("validation must be GovernanceValidation")
        if validation.target_snapshot_id != snapshot_id:
            raise ControlPlaneError("validation targets a different governance snapshot")
        proposal = self._proposal_by_snapshot[snapshot_id]
        if validation.proposal_id != proposal.proposal_id:
            raise ControlPlaneError("validation targets a different proposal identity")
        if validation.validation_id in self._validations:
            raise ControlPlaneError("validation identity is already registered")
        self._validations[validation.validation_id] = validation
        self._validation_by_snapshot[snapshot_id] = validation
        if not validation.passed:
            return self._append_transition(
                snapshot_id,
                GovernanceLifecycleState.QUARANTINED,
                LifecycleEvent.QUALIFICATION_FAILED,
                validation.validation_id,
            )
        return self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.VALIDATED,
            LifecycleEvent.VALIDATE,
            validation.validation_id,
        )

    def _check_promotion_lineage(self, snapshot: GovernanceSnapshot) -> None:
        if self._active_snapshot_id is None:
            if (
                snapshot.previous_snapshot_id is not None
                or snapshot.supersedes_snapshot_id is not None
            ):
                raise ControlPlaneError(
                    "initial promotion cannot claim an untracked predecessor"
                )
            return
        if (
            snapshot.previous_snapshot_id != self._active_snapshot_id
            or snapshot.supersedes_snapshot_id != self._active_snapshot_id
        ):
            raise ControlPlaneError(
                "promotion lineage must exactly bind the active snapshot"
            )

    def promote_snapshot(
        self, snapshot_id: str, decision: AuthorityDecision
    ) -> LifecycleTransition:
        self._require_state(snapshot_id, GovernanceLifecycleState.VALIDATED)
        governed = self.snapshot(snapshot_id)
        authority = self._check_decision(
            decision,
            action=AuthorityDecisionAction.PROMOTE,
            target_snapshot_id=snapshot_id,
        )
        proposal = self._proposal_by_snapshot[snapshot_id]
        validation = self._validation_by_snapshot[snapshot_id]
        if not validation.passed:
            raise ControlPlaneError("failed validation cannot be promoted")
        if authority.proposal_id != proposal.proposal_id:
            raise UnauthorizedGovernanceDecision(
                "authority decision does not bind the registered proposal"
            )
        if authority.validation_id != validation.validation_id:
            raise UnauthorizedGovernanceDecision(
                "authority decision does not bind the registered validation"
            )
        if snapshot_id not in self._verification_ids:
            raise ControlPlaneError("snapshot lacks authority verification evidence")
        self._check_promotion_lineage(governed)

        previous_active = self._active_snapshot_id
        self._record_decision(authority)
        if previous_active is not None:
            self._append_transition(
                previous_active,
                GovernanceLifecycleState.SUPERSEDED,
                LifecycleEvent.SUPERSEDE,
                authority.decision_id,
                authority.decision_id,
            )
        transition = self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.ACTIVE,
            LifecycleEvent.PROMOTE,
            authority.decision_id,
            authority.decision_id,
        )
        self._active_snapshot_id = snapshot_id
        return transition

    def revoke_snapshot(
        self, snapshot_id: str, decision: AuthorityDecision
    ) -> LifecycleTransition:
        state = self.snapshot_state(snapshot_id)
        if state not in {
            GovernanceLifecycleState.ACTIVE,
            GovernanceLifecycleState.SUPERSEDED,
        }:
            raise InvalidLifecycleTransition(
                "only ACTIVE or SUPERSEDED snapshots can be revoked"
            )
        authority = self._check_decision(
            decision,
            action=AuthorityDecisionAction.REVOKE,
            target_snapshot_id=snapshot_id,
        )
        self._record_decision(authority)
        transition = self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.REVOKED,
            LifecycleEvent.REVOKE,
            authority.decision_id,
            authority.decision_id,
        )
        self._interventions[snapshot_id] = authority
        if self._active_snapshot_id == snapshot_id:
            self._active_snapshot_id = None
        return transition

    def quarantine_snapshot(
        self, snapshot_id: str, decision: AuthorityDecision
    ) -> LifecycleTransition:
        state = self.snapshot_state(snapshot_id)
        if GovernanceLifecycleState.QUARANTINED not in _ALLOWED_TRANSITIONS[state]:
            raise InvalidLifecycleTransition(
                f"snapshot in {state.value} cannot be quarantined"
            )
        authority = self._check_decision(
            decision,
            action=AuthorityDecisionAction.QUARANTINE,
            target_snapshot_id=snapshot_id,
        )
        self._record_decision(authority)
        transition = self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.QUARANTINED,
            LifecycleEvent.QUARANTINE,
            authority.decision_id,
            authority.decision_id,
        )
        self._interventions[snapshot_id] = authority
        if self._active_snapshot_id == snapshot_id:
            self._active_snapshot_id = None
        return transition

    def rollback_to_snapshot(
        self, snapshot_id: str, decision: AuthorityDecision
    ) -> LifecycleTransition:
        self._require_state(snapshot_id, GovernanceLifecycleState.SUPERSEDED)
        if self._active_snapshot_id is None:
            raise InvalidLifecycleTransition(
                "rollback requires a different currently ACTIVE snapshot"
            )
        previous_active = self._active_snapshot_id
        if previous_active == snapshot_id:
            raise InvalidLifecycleTransition("rollback target is already active")
        authority = self._check_decision(
            decision,
            action=AuthorityDecisionAction.ROLLBACK,
            target_snapshot_id=snapshot_id,
        )
        if not any(
            item.to_state is GovernanceLifecycleState.ACTIVE
            for item in self.snapshot_history(snapshot_id)
        ):
            raise InvalidLifecycleTransition(
                "rollback target has no prior audited activation"
            )
        self._record_decision(authority)
        self._append_transition(
            previous_active,
            GovernanceLifecycleState.SUPERSEDED,
            LifecycleEvent.SUPERSEDE,
            authority.decision_id,
            authority.decision_id,
        )
        transition = self._append_transition(
            snapshot_id,
            GovernanceLifecycleState.ACTIVE,
            LifecycleEvent.ROLLBACK,
            authority.decision_id,
            authority.decision_id,
        )
        self._active_snapshot_id = snapshot_id
        return transition

    def _activation_transition(self, snapshot_id: str) -> LifecycleTransition:
        active_events = tuple(
            item
            for item in self.snapshot_history(snapshot_id)
            if item.to_state is GovernanceLifecycleState.ACTIVE
        )
        if not active_events:
            raise ExecutionPinError("active snapshot lacks an activation transition")
        return active_events[-1]

    def pin_execution(
        self, execution_id: str, fingerprint: ExecutionFingerprint
    ) -> ExecutionPin:
        _identifier(execution_id, "execution_id")
        if execution_id in self._execution_pins:
            raise ExecutionPinError(
                "execution identity already has an immutable governance pin"
            )
        if self._active_snapshot_id is None:
            raise ExecutionPinError(
                "normative execution requires one ACTIVE governance snapshot"
            )
        if not isinstance(fingerprint, ExecutionFingerprint):
            raise ExecutionPinError("fingerprint must be ExecutionFingerprint")
        governed = self._snapshots[self._active_snapshot_id]
        if fingerprint.governance_snapshot_identity != governed.snapshot_id:
            raise ExecutionPinError(
                "cross-snapshot execution fingerprint mutation is forbidden"
            )
        activation = self._activation_transition(governed.snapshot_id)
        pin = ExecutionPin(
            execution_id=execution_id,
            governance_snapshot_id=governed.snapshot_id,
            governance_snapshot_sha256=governed.snapshot_sha256,
            execution_fingerprint=fingerprint,
            activation_transition_id=activation.transition_id,
        )
        self._execution_pins[execution_id] = pin
        return pin

    def start_execution(
        self,
        execution_id: str,
        *,
        factory_source_identity: str,
        requirement_identity: str,
        evidence_snapshot_identity: str,
        tool_config_identity: str,
    ) -> ExecutionPin:
        if self.active_snapshot is None:
            raise ExecutionPinError(
                "normative execution requires one ACTIVE governance snapshot"
            )
        fingerprint = ExecutionFingerprint.for_snapshot(
            factory_source_identity=factory_source_identity,
            requirement_identity=requirement_identity,
            governance_snapshot=self.active_snapshot,
            evidence_snapshot_identity=evidence_snapshot_identity,
            tool_config_identity=tool_config_identity,
        )
        return self.pin_execution(execution_id, fingerprint)

    def require_execution_pin(self, execution_id: str) -> ExecutionPin:
        _identifier(execution_id, "execution_id")
        try:
            return self._execution_pins[execution_id]
        except KeyError as exc:
            raise ExecutionPinError(
                "normative execution is forbidden before governance pinning"
            ) from exc

    def assert_execution_snapshot(
        self, execution_id: str, snapshot_id: str
    ) -> ExecutionPin:
        _identifier(snapshot_id, "snapshot_id")
        pin = self.require_execution_pin(execution_id)
        if pin.governance_snapshot_id != snapshot_id:
            raise ExecutionPinError(
                "cross-snapshot execution mutation is forbidden; start a new execution"
            )
        return pin

    def classify_execution(self, execution_id: str) -> ExecutionClassification:
        pin = self.require_execution_pin(execution_id)
        decision = self._interventions.get(pin.governance_snapshot_id)
        disposition = (
            decision.execution_disposition
            if decision is not None
            else ExecutionDisposition.CONTINUE
        )
        if disposition is None:  # Defensive; intervention decisions require one.
            raise ControlPlaneError("intervention lacks execution disposition")
        return ExecutionClassification(
            execution_id=pin.execution_id,
            execution_pin_id=pin.pin_id,
            governance_snapshot_id=pin.governance_snapshot_id,
            disposition=disposition,
            authority_decision_id=(decision.decision_id if decision is not None else None),
        )

    def classify_pinned_executions(
        self, snapshot_id: str | None = None
    ) -> tuple[ExecutionClassification, ...]:
        if snapshot_id is not None:
            self.snapshot(snapshot_id)
        execution_ids = tuple(
            execution_id
            for execution_id, pin in sorted(self._execution_pins.items())
            if snapshot_id is None or pin.governance_snapshot_id == snapshot_id
        )
        return tuple(self.classify_execution(item) for item in execution_ids)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "active_snapshot_id": self._active_snapshot_id,
            "authority_decisions": [
                self._decisions[decision_id].to_dict()
                for decision_id in sorted(self._decisions)
            ],
            "authority_registry_ids": list(self.authority_registry_ids),
            "authority_verifications": [
                {
                    "authority_registry_id": self._verification_registry_ids[
                        snapshot_id
                    ],
                    "snapshot_id": snapshot_id,
                    "verification_ids": list(self._verification_ids[snapshot_id]),
                }
                for snapshot_id in sorted(self._verification_ids)
            ],
            "decision_authority_ids": list(self.decision_authority_ids),
            "execution_classifications": [
                item.to_dict() for item in self.classify_pinned_executions()
            ],
            "execution_pins": [item.to_dict() for item in self.execution_pins],
            "proposals": [
                self._proposals[proposal_id].to_dict()
                for proposal_id in sorted(self._proposals)
            ],
            "schema_version": self.schema_version,
            "snapshots": [
                self._snapshots[snapshot_id].to_dict()
                for snapshot_id in self.snapshot_ids
            ],
            "snapshot_states": [
                {
                    "snapshot_id": snapshot_id,
                    "state": self._states[snapshot_id].value,
                }
                for snapshot_id in self.snapshot_ids
            ],
            "transitions": [item.to_dict() for item in self.transition_history],
            "validations": [
                self._validations[validation_id].to_dict()
                for validation_id in sorted(self._validations)
            ],
        }

    @property
    def control_plane_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "control_plane_sha256": self.control_plane_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    # Compact operation aliases preserve one state machine and one set of checks.
    observe = observe_snapshot
    verify = verify_snapshot
    propose = propose_snapshot
    validate = validate_snapshot
    promote = promote_snapshot
    revoke = revoke_snapshot
    quarantine = quarantine_snapshot
    rollback = rollback_to_snapshot
    pin = pin_execution


# Naming aliases make the governed nature explicit without parallel contracts.
ControlPlane = GovernanceControlPlane
GovernedAuthorityDecision = AuthorityDecision
GovernedProposal = GovernanceProposal
GovernedValidation = GovernanceValidation
