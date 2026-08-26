"""Deterministic, local source-authority verification.

External bytes enter this module as observations, never as authority.  A
repository-supplied :class:`AuthorityRegistry` is the only public operation
that can produce an ``AUTHORITY_VERIFIED`` result.  Exact revision and content
identity comparisons reuse the M2.4 provenance/freshness vocabulary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Iterable, Mapping

from factory.documentation import Freshness, ProvenanceBinding, canonical_json, canonical_sha256

from .snapshots import GovernanceModelError, GovernanceSourceBinding


class SourceVerificationError(GovernanceModelError):
    """Raised when source authority data cannot be verified unambiguously."""


class UnsupportedSourceTransition(SourceVerificationError):
    """Raised when a caller attempts to assert a lifecycle transition."""


class GovernanceLifecycleState(str, Enum):
    """Canonical governance lifecycle vocabulary.

    Source observations and registry verification control only the first
    transition.  Later transitions are accepted exclusively by the governed
    M2.5D control plane, not by caller mutation of a source-verification value.
    """

    OBSERVED_UNVERIFIED = "OBSERVED_UNVERIFIED"
    AUTHORITY_VERIFIED = "AUTHORITY_VERIFIED"
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    QUARANTINED = "QUARANTINED"


class AuthorityVerificationMethod(str, Enum):
    """Deterministic verification contracts supported by this stage."""

    PINNED_REVISION_SHA256 = "PINNED_REVISION_SHA256"


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 identity of exact caller-supplied bytes."""
    if not isinstance(content, bytes):
        raise SourceVerificationError("content must be exact bytes")
    return hashlib.sha256(content).hexdigest()


def _validated_binding(
    *,
    authority_id: str,
    source_id: str,
    revision: str,
    content_sha256: str,
    source_type: str,
) -> GovernanceSourceBinding:
    try:
        return GovernanceSourceBinding(
            authority_id=authority_id,
            source_id=source_id,
            revision=revision,
            content_sha256=content_sha256,
            source_type=source_type,
        )
    except GovernanceModelError as exc:
        raise SourceVerificationError(str(exc)) from exc


@dataclass(frozen=True)
class SourceMetadata:
    """Claimed metadata accompanying exact observed source bytes.

    This object is descriptive only.  Constructing it does not verify the
    authority claim and cannot create an authoritative provenance binding.
    """

    authority_id: str
    source_id: str
    revision: str
    content_sha256: str
    source_type: str

    def __post_init__(self) -> None:
        _validated_binding(
            authority_id=self.authority_id,
            source_id=self.source_id,
            revision=self.revision,
            content_sha256=self.content_sha256,
            source_type=self.source_type,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "authority_id": self.authority_id,
            "content_sha256": self.content_sha256,
            "revision": self.revision,
            "source_id": self.source_id,
            "source_type": self.source_type,
        }


@dataclass(frozen=True, init=False)
class SourceObservation:
    """Immutable local observation whose initial state cannot be overridden."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.source-observation.v1"

    metadata: SourceMetadata
    observed_content_sha256: str
    _observation_sha256: str = field(repr=False, compare=False)

    def __init__(self, content: bytes, metadata: SourceMetadata) -> None:
        if not isinstance(metadata, SourceMetadata):
            raise SourceVerificationError("metadata must be SourceMetadata")
        observed_digest = sha256_bytes(content)
        if observed_digest != metadata.content_sha256:
            raise SourceVerificationError(
                "metadata content_sha256 does not match caller-supplied bytes"
            )
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "observed_content_sha256", observed_digest)
        object.__setattr__(
            self,
            "_observation_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @classmethod
    def from_bytes(cls, content: bytes, metadata: SourceMetadata) -> SourceObservation:
        return cls(content, metadata)

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def lifecycle_state(self) -> GovernanceLifecycleState:
        return GovernanceLifecycleState.OBSERVED_UNVERIFIED

    @property
    def state(self) -> GovernanceLifecycleState:
        return self.lifecycle_state

    @property
    def authority_id(self) -> str:
        return self.metadata.authority_id

    @property
    def source_id(self) -> str:
        return self.metadata.source_id

    @property
    def revision(self) -> str:
        return self.metadata.revision

    @property
    def content_sha256(self) -> str:
        return self.metadata.content_sha256

    @property
    def source_type(self) -> str:
        return self.metadata.source_type

    @property
    def observation_sha256(self) -> str:
        return self._observation_sha256

    @property
    def identity_sha256(self) -> str:
        return self.observation_sha256

    @property
    def observation_id(self) -> str:
        return f"SOURCE-OBSERVATION-{self.observation_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "lifecycle_state": self.lifecycle_state.value,
            "metadata": self.metadata.to_dict(),
            "observed_content_sha256": self.observed_content_sha256,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "observation_id": self.observation_id,
            "observation_sha256": self.observation_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def transition_to(self, target: GovernanceLifecycleState) -> None:
        if not isinstance(target, GovernanceLifecycleState):
            raise UnsupportedSourceTransition(
                "target must use the canonical GovernanceLifecycleState vocabulary"
            )
        raise UnsupportedSourceTransition(
            f"{self.lifecycle_state.value} -> {target.value} requires a governed "
            "registry or later-stage authority transition"
        )


@dataclass(frozen=True)
class SourceAuthorityContract:
    """Pinned accepted authority and exact current source identity."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.source-authority-contract.v1"

    authority_id: str
    source_id: str
    revision: str
    content_sha256: str
    source_type: str
    verification_method: AuthorityVerificationMethod = (
        AuthorityVerificationMethod.PINNED_REVISION_SHA256
    )
    _contract_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _validated_binding(
            authority_id=self.authority_id,
            source_id=self.source_id,
            revision=self.revision,
            content_sha256=self.content_sha256,
            source_type=self.source_type,
        )
        if not isinstance(self.verification_method, AuthorityVerificationMethod):
            raise SourceVerificationError(
                "verification_method must use AuthorityVerificationMethod"
            )
        object.__setattr__(
            self,
            "_contract_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def contract_sha256(self) -> str:
        return self._contract_sha256

    @property
    def identity_sha256(self) -> str:
        return self.contract_sha256

    @property
    def contract_id(self) -> str:
        return f"SOURCE-AUTHORITY-CONTRACT-{self.contract_sha256}"

    def identity_payload(self) -> dict[str, str]:
        return {
            "authority_id": self.authority_id,
            "content_sha256": self.content_sha256,
            "revision": self.revision,
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "verification_method": self.verification_method.value,
        }

    def to_dict(self) -> dict[str, str]:
        return {
            **self.identity_payload(),
            "contract_id": self.contract_id,
            "contract_sha256": self.contract_sha256,
        }

    def to_provenance(self) -> ProvenanceBinding:
        return ProvenanceBinding(
            source_id=self.source_id,
            revision=self.revision,
            content_sha256=self.content_sha256,
            source_type=self.source_type,
        )

    def to_source_binding(self) -> GovernanceSourceBinding:
        return GovernanceSourceBinding.from_provenance(self.authority_id, self.to_provenance())


_REGISTRY_VERIFICATION_TOKEN = object()


@dataclass(frozen=True, init=False)
class SourceVerification:
    """Reproducible result created only by an authority registry check."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.source-verification.v1"

    observation_id: str
    authority_contract_id: str
    authority_registry_id: str
    lifecycle_state: GovernanceLifecycleState
    freshness: Freshness
    changed_components: tuple[str, ...]
    _source_binding: GovernanceSourceBinding | None = field(repr=False)
    _verification_sha256: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        _token: object,
        observation_id: str,
        authority_contract_id: str,
        authority_registry_id: str,
        lifecycle_state: GovernanceLifecycleState,
        freshness: Freshness,
        changed_components: tuple[str, ...],
        source_binding: GovernanceSourceBinding | None,
    ) -> None:
        if _token is not _REGISTRY_VERIFICATION_TOKEN:
            raise SourceVerificationError(
                "SourceVerification must be created by AuthorityRegistry.verify"
            )
        object.__setattr__(self, "observation_id", observation_id)
        object.__setattr__(self, "authority_contract_id", authority_contract_id)
        object.__setattr__(self, "authority_registry_id", authority_registry_id)
        object.__setattr__(self, "lifecycle_state", lifecycle_state)
        object.__setattr__(self, "freshness", freshness)
        object.__setattr__(self, "changed_components", tuple(changed_components))
        object.__setattr__(self, "_source_binding", source_binding)
        self._validate_result()
        object.__setattr__(
            self,
            "_verification_sha256",
            canonical_sha256(self.identity_payload()),
        )

    def _validate_result(self) -> None:
        if self.lifecycle_state is GovernanceLifecycleState.AUTHORITY_VERIFIED:
            if self.freshness is not Freshness.CURRENT or self._source_binding is None:
                raise SourceVerificationError(
                    "AUTHORITY_VERIFIED requires current authoritative provenance"
                )
            if self.changed_components:
                raise SourceVerificationError(
                    "AUTHORITY_VERIFIED cannot contain changed source components"
                )
        elif self.lifecycle_state is GovernanceLifecycleState.OBSERVED_UNVERIFIED:
            if self.freshness is not Freshness.STALE or self._source_binding is not None:
                raise SourceVerificationError("stale observations must remain OBSERVED_UNVERIFIED")
            if not self.changed_components:
                raise SourceVerificationError(
                    "stale observations must identify changed source components"
                )
        else:
            raise SourceVerificationError(
                "M2.5B source verification cannot create later lifecycle states"
            )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def state(self) -> GovernanceLifecycleState:
        return self.lifecycle_state

    @property
    def is_authority_verified(self) -> bool:
        return self.lifecycle_state is GovernanceLifecycleState.AUTHORITY_VERIFIED

    @property
    def source_binding(self) -> GovernanceSourceBinding | None:
        return self._source_binding

    @property
    def verification_sha256(self) -> str:
        return self._verification_sha256

    @property
    def identity_sha256(self) -> str:
        return self.verification_sha256

    @property
    def verification_id(self) -> str:
        return f"SOURCE-VERIFICATION-{self.verification_sha256}"

    def require_authoritative_binding(self) -> GovernanceSourceBinding:
        if not self.is_authority_verified or self._source_binding is None:
            raise SourceVerificationError("observation has no current authoritative source binding")
        return self._source_binding

    def to_provenance(self) -> ProvenanceBinding:
        return self.require_authoritative_binding().to_provenance()

    def identity_payload(self) -> dict[str, Any]:
        return {
            "authority_contract_id": self.authority_contract_id,
            "authority_registry_id": self.authority_registry_id,
            "changed_components": list(self.changed_components),
            "freshness": self.freshness.value,
            "lifecycle_state": self.lifecycle_state.value,
            "observation_id": self.observation_id,
            "schema_version": self.schema_version,
            "source_binding": (
                self._source_binding.to_dict() if self._source_binding is not None else None
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "verification_id": self.verification_id,
            "verification_sha256": self.verification_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def transition_to(self, target: GovernanceLifecycleState) -> None:
        if not isinstance(target, GovernanceLifecycleState):
            raise UnsupportedSourceTransition(
                "target must use the canonical GovernanceLifecycleState vocabulary"
            )
        raise UnsupportedSourceTransition(
            f"{self.lifecycle_state.value} -> {target.value} is not a source-verification "
            "transition"
        )


@dataclass(frozen=True)
class AuthorityRegistry:
    """Immutable set of accepted authority/source/current-identity contracts."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.authority-registry.v1"

    contracts: tuple[SourceAuthorityContract, ...]
    _by_source_id: Mapping[str, SourceAuthorityContract] = field(
        init=False, repr=False, compare=False
    )
    _registry_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if isinstance(self.contracts, (str, bytes)):
            raise SourceVerificationError("contracts must be a collection")
        try:
            contracts = tuple(self.contracts)
        except TypeError as exc:
            raise SourceVerificationError("contracts must be a collection") from exc
        if not contracts:
            raise SourceVerificationError("authority registry requires contracts")
        if any(not isinstance(item, SourceAuthorityContract) for item in contracts):
            raise SourceVerificationError("contracts must contain SourceAuthorityContract values")

        by_source: dict[str, SourceAuthorityContract] = {}
        for contract in contracts:
            previous = by_source.get(contract.source_id)
            if previous is not None:
                kind = "duplicate" if previous == contract else "conflicting"
                raise SourceVerificationError(
                    f"{kind} authority contract identity for source_id: {contract.source_id}"
                )
            by_source[contract.source_id] = contract

        normalized = tuple(
            sorted(
                contracts,
                key=lambda item: (
                    item.source_id,
                    item.authority_id,
                    item.source_type,
                    item.revision,
                    item.content_sha256,
                ),
            )
        )
        object.__setattr__(self, "contracts", normalized)
        object.__setattr__(
            self,
            "_by_source_id",
            MappingProxyType({item.source_id: item for item in normalized}),
        )
        object.__setattr__(
            self,
            "_registry_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def registry_sha256(self) -> str:
        return self._registry_sha256

    @property
    def identity_sha256(self) -> str:
        return self.registry_sha256

    @property
    def registry_id(self) -> str:
        return f"AUTHORITY-REGISTRY-{self.registry_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contracts": [item.identity_payload() for item in self.contracts],
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "registry_id": self.registry_id,
            "registry_sha256": self.registry_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def contract_for(self, source_id: str) -> SourceAuthorityContract:
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or source_id != source_id.strip()
        ):
            raise SourceVerificationError("source_id must be a non-empty stable identifier")
        try:
            return self._by_source_id[source_id]
        except KeyError as exc:
            raise SourceVerificationError(f"unregistered source authority: {source_id}") from exc

    def current_sources(self) -> dict[str, tuple[str, str]]:
        """Return the exact mapping consumed by M2.4 freshness checks."""
        return {item.source_id: (item.revision, item.content_sha256) for item in self.contracts}

    def freshness_of(self, binding: ProvenanceBinding | GovernanceSourceBinding) -> Freshness:
        if isinstance(binding, GovernanceSourceBinding):
            provenance = binding.to_provenance()
            try:
                contract = self.contract_for(binding.source_id)
            except SourceVerificationError:
                return Freshness.STALE
            if binding.authority_id != contract.authority_id:
                return Freshness.STALE
        elif isinstance(binding, ProvenanceBinding):
            provenance = binding
            try:
                contract = self.contract_for(binding.source_id)
            except SourceVerificationError:
                return Freshness.STALE
        else:
            raise SourceVerificationError(
                "binding must be ProvenanceBinding or GovernanceSourceBinding"
            )
        if provenance.source_type != contract.source_type:
            return Freshness.STALE
        return provenance.freshness_against(self.current_sources())

    def verify(self, observation: SourceObservation) -> SourceVerification:
        if not isinstance(observation, SourceObservation):
            raise SourceVerificationError("observation must be SourceObservation")
        contract = self.contract_for(observation.source_id)
        if observation.authority_id != contract.authority_id:
            raise SourceVerificationError(
                f"invalid authority for source_id: {observation.source_id}"
            )
        if observation.source_type != contract.source_type:
            raise SourceVerificationError(
                f"invalid source type for source_id: {observation.source_id}"
            )

        observed_provenance = ProvenanceBinding(
            source_id=observation.source_id,
            revision=observation.revision,
            content_sha256=observation.content_sha256,
            source_type=observation.source_type,
        )
        freshness = observed_provenance.freshness_against(self.current_sources())
        changed_components = tuple(
            name
            for name, changed in (
                ("REVISION", observation.revision != contract.revision),
                ("CONTENT_SHA256", observation.content_sha256 != contract.content_sha256),
            )
            if changed
        )
        is_current = freshness is Freshness.CURRENT
        source_binding = (
            GovernanceSourceBinding.from_provenance(contract.authority_id, observed_provenance)
            if is_current
            else None
        )
        return SourceVerification(
            _token=_REGISTRY_VERIFICATION_TOKEN,
            observation_id=observation.observation_id,
            authority_contract_id=contract.contract_id,
            authority_registry_id=self.registry_id,
            lifecycle_state=(
                GovernanceLifecycleState.AUTHORITY_VERIFIED
                if is_current
                else GovernanceLifecycleState.OBSERVED_UNVERIFIED
            ),
            freshness=freshness,
            changed_components=changed_components,
            source_binding=source_binding,
        )

    def verify_many(
        self, observations: Iterable[SourceObservation]
    ) -> tuple[SourceVerification, ...]:
        if isinstance(observations, (str, bytes)):
            raise SourceVerificationError("observations must be a collection")
        try:
            observed = tuple(observations)
        except TypeError as exc:
            raise SourceVerificationError("observations must be a collection") from exc
        if any(not isinstance(item, SourceObservation) for item in observed):
            raise SourceVerificationError("observations must contain SourceObservation values")

        observation_ids: set[str] = set()
        source_revisions: dict[tuple[str, str], str] = {}
        for item in observed:
            if item.observation_id in observation_ids:
                raise SourceVerificationError(
                    f"duplicate observation identity: {item.observation_id}"
                )
            observation_ids.add(item.observation_id)
            key = (item.source_id, item.revision)
            previous_digest = source_revisions.get(key)
            if previous_digest is not None and previous_digest != item.content_sha256:
                raise SourceVerificationError(
                    "conflicting observation identity for source revision: "
                    f"{item.source_id}@{item.revision}"
                )
            source_revisions[key] = item.content_sha256

        return tuple(
            sorted(
                (self.verify(item) for item in observed),
                key=lambda item: item.observation_id,
            )
        )


# Concise vocabulary aliases without creating competing contracts.
AuthorityContract = SourceAuthorityContract
ObservationState = GovernanceLifecycleState
SourceLifecycleState = GovernanceLifecycleState
