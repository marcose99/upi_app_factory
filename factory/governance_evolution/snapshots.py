"""Immutable governance snapshots and execution fingerprints.

The identity functions in this module deliberately reuse the M2.4 canonical
JSON, SHA-256, and provenance contracts.  They accept caller-supplied facts;
they do not discover authority from source text or activate policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable, Mapping, NoReturn, cast

from factory.documentation import ProvenanceBinding, canonical_json, canonical_sha256
from factory.documentation.facts import FactModelError


class GovernanceModelError(ValueError):
    """Raised when immutable governance identity data is invalid."""


class _FrozenDict(dict[str, Any]):
    """A JSON-compatible dictionary that rejects ordinary in-place mutation."""

    def _immutable(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise TypeError("governed JSON data is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


def _stable_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise GovernanceModelError(f"{field_name} must be a non-empty stable identifier")
    return value


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _stable_identifier(value, field_name)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return _FrozenDict(
            {key: _freeze_json(item) for key, item in sorted(value.items())}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _canonical_object(value: Mapping[str, Any], field_name: str) -> tuple[Mapping[str, Any], str]:
    """Detach, normalize, and deeply freeze a caller-owned JSON object."""
    try:
        encoded = canonical_json(dict(value))
    except FactModelError as exc:
        raise GovernanceModelError(f"{field_name} must contain canonical JSON data") from exc
    detached = json.loads(encoded)
    if not isinstance(detached, dict):  # Defensive: ``dict(value)`` should guarantee this.
        raise GovernanceModelError(f"{field_name} must be a JSON object")
    return cast(Mapping[str, Any], _freeze_json(detached)), encoded


@dataclass(frozen=True)
class GovernanceSourceBinding:
    """Explicit authority plus the exact M2.4-compatible source revision.

    ``authority_id`` is caller-supplied governed data.  The remaining fields
    map exactly to :class:`factory.documentation.ProvenanceBinding`; no field is
    inferred from prose or source contents.
    """

    authority_id: str
    source_id: str
    revision: str
    content_sha256: str
    source_type: str

    def __post_init__(self) -> None:
        _stable_identifier(self.authority_id, "authority_id")
        try:
            ProvenanceBinding(
                source_id=self.source_id,
                revision=self.revision,
                content_sha256=self.content_sha256,
                source_type=self.source_type,
            )
        except FactModelError as exc:
            raise GovernanceModelError(str(exc)) from exc

    @classmethod
    def from_provenance(
        cls, authority_id: str, binding: ProvenanceBinding
    ) -> GovernanceSourceBinding:
        if not isinstance(binding, ProvenanceBinding):
            raise GovernanceModelError("binding must be an M2.4 ProvenanceBinding")
        return cls(
            authority_id=authority_id,
            source_id=binding.source_id,
            revision=binding.revision,
            content_sha256=binding.content_sha256,
            source_type=binding.source_type,
        )

    def to_provenance(self) -> ProvenanceBinding:
        return ProvenanceBinding(
            source_id=self.source_id,
            revision=self.revision,
            content_sha256=self.content_sha256,
            source_type=self.source_type,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "authority_id": self.authority_id,
            **self.to_provenance().to_dict(),
        }


@dataclass(frozen=True)
class GovernanceSnapshot:
    """A deeply immutable, provenance-bound governance bundle.

    ``previous_snapshot_id`` records immediate bundle lineage, while
    ``supersedes_snapshot_id`` records the snapshot this bundle explicitly
    replaces.  Both are canonical data.  Constructing a successor therefore
    creates a distinct object and cannot rewrite its predecessor.
    """

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-snapshot.v1"

    version_id: str
    payload: Mapping[str, Any]
    source_bindings: tuple[GovernanceSourceBinding, ...]
    previous_snapshot_id: str | None = None
    supersedes_snapshot_id: str | None = None
    _payload_json: str = field(init=False, repr=False, compare=False)
    _payload_sha256: str = field(init=False, repr=False, compare=False)
    _snapshot_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _stable_identifier(self.version_id, "version_id")
        _optional_identifier(self.previous_snapshot_id, "previous_snapshot_id")
        _optional_identifier(self.supersedes_snapshot_id, "supersedes_snapshot_id")
        if not isinstance(self.payload, Mapping):
            raise GovernanceModelError("payload must be a canonical JSON object")

        frozen_payload, payload_json = _canonical_object(self.payload, "payload")
        bindings = self._normalize_bindings(self.source_bindings)
        object.__setattr__(self, "payload", frozen_payload)
        object.__setattr__(self, "source_bindings", bindings)
        object.__setattr__(self, "_payload_json", payload_json)
        object.__setattr__(
            self,
            "_payload_sha256",
            canonical_sha256(json.loads(payload_json)),
        )
        object.__setattr__(
            self,
            "_snapshot_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @staticmethod
    def _normalize_bindings(
        values: Iterable[GovernanceSourceBinding],
    ) -> tuple[GovernanceSourceBinding, ...]:
        if isinstance(values, (str, bytes)):
            raise GovernanceModelError("source_bindings must be a collection")
        try:
            bindings = tuple(values)
        except TypeError as exc:
            raise GovernanceModelError("source_bindings must be a collection") from exc
        if not bindings:
            raise GovernanceModelError("a governance snapshot requires source_bindings")
        if any(not isinstance(item, GovernanceSourceBinding) for item in bindings):
            raise GovernanceModelError(
                "source_bindings must contain GovernanceSourceBinding values"
            )
        source_ids = [item.source_id for item in bindings]
        if len(source_ids) != len(set(source_ids)):
            raise GovernanceModelError("source binding source_id values must be unique")
        return tuple(
            sorted(
                bindings,
                key=lambda item: (
                    item.source_id,
                    item.authority_id,
                    item.revision,
                    item.content_sha256,
                    item.source_type,
                ),
            )
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def payload_sha256(self) -> str:
        return self._payload_sha256

    @property
    def snapshot_sha256(self) -> str:
        return self._snapshot_sha256

    @property
    def identity_sha256(self) -> str:
        return self.snapshot_sha256

    @property
    def snapshot_id(self) -> str:
        return f"GOVERNANCE-SNAPSHOT-{self.snapshot_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "payload": json.loads(self._payload_json),
            "previous_snapshot_id": self.previous_snapshot_id,
            "schema_version": self.schema_version,
            "source_bindings": [item.to_dict() for item in self.source_bindings],
            "supersedes_snapshot_id": self.supersedes_snapshot_id,
            "version_id": self.version_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "payload_sha256": self.payload_sha256,
            "snapshot_id": self.snapshot_id,
            "snapshot_sha256": self.snapshot_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def __hash__(self) -> int:
        return hash(self.snapshot_id)


@dataclass(frozen=True)
class ExecutionFingerprint:
    """Versioned identity of every mandatory deterministic execution input."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.execution-fingerprint.v1"

    factory_source_identity: str
    requirement_identity: str
    governance_snapshot_identity: str
    evidence_snapshot_identity: str
    tool_config_identity: str
    _fingerprint_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for field_name in (
            "factory_source_identity",
            "requirement_identity",
            "governance_snapshot_identity",
            "evidence_snapshot_identity",
            "tool_config_identity",
        ):
            _stable_identifier(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "_fingerprint_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @classmethod
    def for_snapshot(
        cls,
        *,
        factory_source_identity: str,
        requirement_identity: str,
        governance_snapshot: GovernanceSnapshot,
        evidence_snapshot_identity: str,
        tool_config_identity: str,
    ) -> ExecutionFingerprint:
        if not isinstance(governance_snapshot, GovernanceSnapshot):
            raise GovernanceModelError(
                "governance_snapshot must be an immutable GovernanceSnapshot"
            )
        return cls(
            factory_source_identity=factory_source_identity,
            requirement_identity=requirement_identity,
            governance_snapshot_identity=governance_snapshot.snapshot_id,
            evidence_snapshot_identity=evidence_snapshot_identity,
            tool_config_identity=tool_config_identity,
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def fingerprint_sha256(self) -> str:
        return self._fingerprint_sha256

    @property
    def identity_sha256(self) -> str:
        return self.fingerprint_sha256

    @property
    def fingerprint_id(self) -> str:
        return f"EXECUTION-FINGERPRINT-{self.fingerprint_sha256}"

    def identity_payload(self) -> dict[str, str]:
        return {
            "evidence_snapshot_identity": self.evidence_snapshot_identity,
            "factory_source_identity": self.factory_source_identity,
            "governance_snapshot_identity": self.governance_snapshot_identity,
            "requirement_identity": self.requirement_identity,
            "schema_version": self.schema_version,
            "tool_config_identity": self.tool_config_identity,
        }

    def to_dict(self) -> dict[str, str]:
        return {
            **self.identity_payload(),
            "fingerprint_id": self.fingerprint_id,
            "fingerprint_sha256": self.fingerprint_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


# Vocabulary aliases keep "bundle" and "source binding" terminology explicit
# without introducing distinct identity contracts for the same governed object.
GovernanceBundle = GovernanceSnapshot
SourceBinding = GovernanceSourceBinding
