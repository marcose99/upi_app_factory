"""Canonical governance semantic differences and evidence-backed impact.

This module compares only explicitly supported governed entity collections.  It
does not compare narrative summaries and it does not infer relationships from
names or prose.  Reverse impact is projected only over relationships already
accepted by the M2.4 :class:`~factory.documentation.EvidenceGraph`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Iterable, Mapping, cast

from factory.documentation import (
    EvidenceGraph,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from factory.documentation.facts import FactModelError

from .snapshots import GovernanceModelError, GovernanceSnapshot, _freeze_json


class ImpactModelError(GovernanceModelError):
    """Raised when semantic or impact inputs are ambiguous or invalid."""


class GovernedEntityType(str, Enum):
    """Governed entity kinds eligible for deterministic semantic comparison."""

    FACT = "FACT"
    RULE = "RULE"
    CAPABILITY = "CAPABILITY"
    TEMPLATE = "TEMPLATE"
    GENERATED_APPLICATION_PROVENANCE = "GENERATED_APPLICATION_PROVENANCE"


class SemanticChangeKind(str, Enum):
    """Stable semantic change classifications."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CHANGED = "CHANGED"


_SECTION_CONTRACTS: tuple[tuple[str, GovernedEntityType, str], ...] = (
    ("facts", GovernedEntityType.FACT, "fact_id"),
    ("rules", GovernedEntityType.RULE, "rule_id"),
    ("capabilities", GovernedEntityType.CAPABILITY, "capability_id"),
    ("templates", GovernedEntityType.TEMPLATE, "template_id"),
    (
        "generated_application_provenance",
        GovernedEntityType.GENERATED_APPLICATION_PROVENANCE,
        "provenance_id",
    ),
)

_GRAPH_NODE_TYPES: dict[str, GovernedEntityType] = {
    "FACT": GovernedEntityType.FACT,
    "GOVERNANCE_FACT": GovernedEntityType.FACT,
    "RULE": GovernedEntityType.RULE,
    "GOVERNANCE_RULE": GovernedEntityType.RULE,
    "CAPABILITY": GovernedEntityType.CAPABILITY,
    "FACTORY_CAPABILITY": GovernedEntityType.CAPABILITY,
    "APPLICATION_CAPABILITY": GovernedEntityType.CAPABILITY,
    "TEMPLATE": GovernedEntityType.TEMPLATE,
    "GENERATOR_TEMPLATE": GovernedEntityType.TEMPLATE,
    "GENERATED_APPLICATION": GovernedEntityType.GENERATED_APPLICATION_PROVENANCE,
    "GENERATED_APPLICATION_PROVENANCE": (GovernedEntityType.GENERATED_APPLICATION_PROVENANCE),
    "APPLICATION_PROVENANCE": GovernedEntityType.GENERATED_APPLICATION_PROVENANCE,
}


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ImpactModelError(f"{field_name} must be a non-empty stable identifier")
    return value


def _canonical_value(value: Any, field_name: str) -> Any:
    """Detach and deeply freeze JSON data using the M2.4 canonical contract."""
    try:
        detached = json.loads(canonical_json(value))
    except FactModelError as exc:
        raise ImpactModelError(f"{field_name} must contain canonical JSON data") from exc
    return _freeze_json(detached)


def _detached(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _entity_sort_key(change: SemanticChange) -> tuple[str, str]:
    return (change.entity_type.value, change.entity_id)


def _normalize_entity_value(value: Any, identity_field: str) -> Any:
    """Remove a redundant collection identity from an entity's semantic body."""
    if isinstance(value, Mapping):
        normalized = dict(value)
        normalized.pop(identity_field, None)
        return _canonical_value(normalized, "governed entity")
    return _canonical_value(value, "governed entity")


def _index_section(
    section: Any,
    *,
    section_name: str,
    entity_type: GovernedEntityType,
    identity_field: str,
) -> dict[tuple[GovernedEntityType, str], Any]:
    indexed: dict[tuple[GovernedEntityType, str], Any] = {}

    if isinstance(section, Mapping):
        candidates: Iterable[tuple[object, Any]] = section.items()
        from_mapping = True
    elif isinstance(section, (list, tuple)):
        candidates = enumerate(section)
        from_mapping = False
    else:
        raise ImpactModelError(
            f"payload section {section_name} must be an ID-keyed object or entity list"
        )

    for key_or_index, candidate in candidates:
        if from_mapping:
            entity_id = _identifier(key_or_index, f"{section_name} entity ID")
            if isinstance(candidate, Mapping) and identity_field in candidate:
                embedded_id = _identifier(
                    candidate[identity_field], f"{section_name}.{identity_field}"
                )
                if embedded_id != entity_id:
                    raise ImpactModelError(
                        f"payload section {section_name} has conflicting entity ID: "
                        f"{entity_id} != {embedded_id}"
                    )
            semantic_value = _normalize_entity_value(candidate, identity_field)
        elif isinstance(candidate, str):
            entity_id = _identifier(candidate, f"{section_name} entity ID")
            semantic_value = _canonical_value({}, "governed entity")
        elif isinstance(candidate, Mapping):
            if identity_field not in candidate:
                raise ImpactModelError(
                    f"payload section {section_name} list entries require {identity_field}"
                )
            entity_id = _identifier(candidate[identity_field], f"{section_name}.{identity_field}")
            semantic_value = _normalize_entity_value(candidate, identity_field)
        else:
            raise ImpactModelError(
                f"payload section {section_name} entry {key_or_index} lacks an explicit ID"
            )

        identity = (entity_type, entity_id)
        if identity in indexed:
            raise ImpactModelError(
                f"payload section {section_name} has duplicate entity ID: {entity_id}"
            )
        indexed[identity] = semantic_value
    return indexed


def _index_snapshot(
    snapshot: GovernanceSnapshot,
) -> dict[tuple[GovernedEntityType, str], Any]:
    if not isinstance(snapshot, GovernanceSnapshot):
        raise ImpactModelError("semantic diff inputs must be immutable GovernanceSnapshot values")
    indexed: dict[tuple[GovernedEntityType, str], Any] = {}
    for section_name, entity_type, identity_field in _SECTION_CONTRACTS:
        if section_name not in snapshot.payload:
            continue
        indexed.update(
            _index_section(
                snapshot.payload[section_name],
                section_name=section_name,
                entity_type=entity_type,
                identity_field=identity_field,
            )
        )
    return indexed


@dataclass(frozen=True)
class SemanticChange:
    """One canonical, stable-ID governance structure change."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.semantic-change.v1"

    kind: SemanticChangeKind
    entity_type: GovernedEntityType
    entity_id: str
    before: Any
    after: Any
    _change_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SemanticChangeKind):
            raise ImpactModelError("kind must use SemanticChangeKind")
        if not isinstance(self.entity_type, GovernedEntityType):
            raise ImpactModelError("entity_type must use GovernedEntityType")
        _identifier(self.entity_id, "entity_id")
        object.__setattr__(self, "before", _canonical_value(self.before, "before"))
        object.__setattr__(self, "after", _canonical_value(self.after, "after"))
        object.__setattr__(
            self,
            "_change_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def classification(self) -> SemanticChangeKind:
        return self.kind

    @property
    def governed_id(self) -> str:
        return self.entity_id

    @property
    def change_sha256(self) -> str:
        return self._change_sha256

    @property
    def change_id(self) -> str:
        return f"SEMANTIC-CHANGE-{self.change_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "after": _detached(self.after),
            "before": _detached(self.before),
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "kind": self.kind.value,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "change_id": self.change_id,
            "change_sha256": self.change_sha256,
        }


@dataclass(frozen=True)
class SemanticDiff:
    """Immutable deterministic difference between two governance snapshots."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-semantic-diff.v1"

    before_snapshot_id: str
    after_snapshot_id: str
    added: tuple[SemanticChange, ...] = ()
    removed: tuple[SemanticChange, ...] = ()
    changed: tuple[SemanticChange, ...] = ()
    _diff_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _identifier(self.before_snapshot_id, "before_snapshot_id")
        _identifier(self.after_snapshot_id, "after_snapshot_id")
        classifications = (
            ("added", SemanticChangeKind.ADDED),
            ("removed", SemanticChangeKind.REMOVED),
            ("changed", SemanticChangeKind.CHANGED),
        )
        normalized: list[SemanticChange] = []
        for field_name, expected_kind in classifications:
            values = getattr(self, field_name)
            if isinstance(values, (str, bytes)):
                raise ImpactModelError(f"{field_name} must be a collection")
            try:
                changes = tuple(values)
            except TypeError as exc:
                raise ImpactModelError(f"{field_name} must be a collection") from exc
            if any(not isinstance(item, SemanticChange) for item in changes):
                raise ImpactModelError(f"{field_name} must contain SemanticChange values")
            if any(item.kind is not expected_kind for item in changes):
                raise ImpactModelError(
                    f"{field_name} contains a change with the wrong classification"
                )
            changes = tuple(sorted(changes, key=_entity_sort_key))
            object.__setattr__(self, field_name, changes)
            normalized.extend(changes)

        identities = [(item.entity_type, item.entity_id) for item in normalized]
        if len(identities) != len(set(identities)):
            raise ImpactModelError("an entity may have only one semantic classification")
        if self.before_snapshot_id == self.after_snapshot_id and normalized:
            raise ImpactModelError("one immutable snapshot identity cannot contain changes")
        object.__setattr__(
            self,
            "_diff_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @classmethod
    def between(cls, before: GovernanceSnapshot, after: GovernanceSnapshot) -> SemanticDiff:
        return diff_governance_snapshots(before, after)

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def is_noop(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def changes(self) -> tuple[SemanticChange, ...]:
        return tuple(sorted((*self.added, *self.removed, *self.changed), key=_entity_sort_key))

    @property
    def added_ids(self) -> tuple[str, ...]:
        return tuple(item.entity_id for item in self.added)

    @property
    def removed_ids(self) -> tuple[str, ...]:
        return tuple(item.entity_id for item in self.removed)

    @property
    def changed_ids(self) -> tuple[str, ...]:
        return tuple(item.entity_id for item in self.changed)

    @property
    def diff_sha256(self) -> str:
        return self._diff_sha256

    @property
    def identity_sha256(self) -> str:
        return self.diff_sha256

    @property
    def diff_id(self) -> str:
        return f"GOVERNANCE-SEMANTIC-DIFF-{self.diff_sha256}"

    def identity_payload(self) -> dict[str, Any]:
        return {
            "added": [item.to_dict() for item in self.added],
            "after_snapshot_id": self.after_snapshot_id,
            "before_snapshot_id": self.before_snapshot_id,
            "changed": [item.to_dict() for item in self.changed],
            "removed": [item.to_dict() for item in self.removed],
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "diff_id": self.diff_id,
            "diff_sha256": self.diff_sha256,
            "is_noop": self.is_noop,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def diff_governance_snapshots(
    before: GovernanceSnapshot, after: GovernanceSnapshot
) -> SemanticDiff:
    """Compare canonical governed entities without reading narrative text."""
    before_index = _index_snapshot(before)
    after_index = _index_snapshot(after)
    before_ids = set(before_index)
    after_ids = set(after_index)

    added = tuple(
        SemanticChange(
            SemanticChangeKind.ADDED,
            entity_type,
            entity_id,
            None,
            after_index[(entity_type, entity_id)],
        )
        for entity_type, entity_id in sorted(
            after_ids - before_ids, key=lambda x: (x[0].value, x[1])
        )
    )
    removed = tuple(
        SemanticChange(
            SemanticChangeKind.REMOVED,
            entity_type,
            entity_id,
            before_index[(entity_type, entity_id)],
            None,
        )
        for entity_type, entity_id in sorted(
            before_ids - after_ids, key=lambda x: (x[0].value, x[1])
        )
    )
    changed = tuple(
        SemanticChange(
            SemanticChangeKind.CHANGED,
            entity_type,
            entity_id,
            before_index[(entity_type, entity_id)],
            after_index[(entity_type, entity_id)],
        )
        for entity_type, entity_id in sorted(
            before_ids & after_ids, key=lambda x: (x[0].value, x[1])
        )
        if canonical_json(before_index[(entity_type, entity_id)])
        != canonical_json(after_index[(entity_type, entity_id)])
    )
    return SemanticDiff(
        before_snapshot_id=before.snapshot_id,
        after_snapshot_id=after.snapshot_id,
        added=added,
        removed=removed,
        changed=changed,
    )


def _normalize_current_sources(
    current_sources: Mapping[str, tuple[str, str]] | None,
) -> tuple[tuple[str, str, str], ...]:
    if current_sources is None:
        return ()
    if not isinstance(current_sources, Mapping):
        raise ImpactModelError("current_sources must be an M2.4 freshness mapping")
    normalized: list[tuple[str, str, str]] = []
    for source_id, identity in current_sources.items():
        if not isinstance(identity, (tuple, list)) or len(identity) != 2:
            raise ImpactModelError(
                "current_sources values must contain revision and content SHA-256"
            )
        revision, content_sha256 = identity
        try:
            binding = ProvenanceBinding(
                source_id=source_id,
                revision=revision,
                content_sha256=content_sha256,
                source_type="GOVERNANCE_IMPACT_FRESHNESS_INPUT",
            )
        except FactModelError as exc:
            raise ImpactModelError(str(exc)) from exc
        normalized.append((binding.source_id, binding.revision, binding.content_sha256))
    return tuple(sorted(normalized))


def _type_buckets() -> dict[GovernedEntityType, set[str]]:
    return {entity_type: set() for entity_type in GovernedEntityType}


@dataclass(frozen=True)
class ImpactProjection:
    """Deterministic reverse impact derived only from supplied graph evidence."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-impact-projection.v1"

    semantic_diff_id: str
    evidence_graph_digest: str | None
    freshness_source_identities: tuple[tuple[str, str, str], ...]
    affected_fact_ids: tuple[str, ...]
    affected_rule_ids: tuple[str, ...]
    affected_capability_ids: tuple[str, ...]
    affected_template_ids: tuple[str, ...]
    affected_generated_application_provenance_ids: tuple[str, ...]
    stale_evidence_ids: tuple[str, ...]
    reverse_transitive_ids: tuple[str, ...]
    unresolved_reference_ids: tuple[str, ...]
    unknown_impact_ids: tuple[str, ...]
    _impact_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _identifier(self.semantic_diff_id, "semantic_diff_id")
        if self.evidence_graph_digest is not None:
            try:
                ProvenanceBinding(
                    "EVIDENCE-GRAPH",
                    "graph:1",
                    self.evidence_graph_digest,
                    "FACT_EVIDENCE_GRAPH",
                )
            except FactModelError as exc:
                raise ImpactModelError("evidence_graph_digest must be a SHA-256 digest") from exc
        tuple_fields = (
            "affected_fact_ids",
            "affected_rule_ids",
            "affected_capability_ids",
            "affected_template_ids",
            "affected_generated_application_provenance_ids",
            "stale_evidence_ids",
            "reverse_transitive_ids",
            "unresolved_reference_ids",
            "unknown_impact_ids",
        )
        normalized_freshness: list[tuple[str, str, str]] = []
        source_ids: set[str] = set()
        for identity in self.freshness_source_identities:
            if not isinstance(identity, (tuple, list)) or len(identity) != 3:
                raise ImpactModelError(
                    "freshness_source_identities must contain source, revision, and digest"
                )
            source_id, revision, content_sha256 = identity
            try:
                binding = ProvenanceBinding(
                    source_id=source_id,
                    revision=revision,
                    content_sha256=content_sha256,
                    source_type="GOVERNANCE_IMPACT_FRESHNESS_INPUT",
                )
            except FactModelError as exc:
                raise ImpactModelError(str(exc)) from exc
            if binding.source_id in source_ids:
                raise ImpactModelError("freshness source identities must use unique source IDs")
            source_ids.add(binding.source_id)
            normalized_freshness.append(
                (binding.source_id, binding.revision, binding.content_sha256)
            )
        object.__setattr__(
            self,
            "freshness_source_identities",
            tuple(sorted(normalized_freshness)),
        )
        for field_name in tuple_fields:
            values = tuple(getattr(self, field_name))
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ImpactModelError(f"{field_name} must contain stable IDs")
            normalized = tuple(sorted(set(values)))
            object.__setattr__(self, field_name, normalized)
        affected_groups = (
            set(self.affected_fact_ids),
            set(self.affected_rule_ids),
            set(self.affected_capability_ids),
            set(self.affected_template_ids),
            set(self.affected_generated_application_provenance_ids),
        )
        affected_count = sum(len(group) for group in affected_groups)
        if affected_count != len(set().union(*affected_groups)):
            raise ImpactModelError("an affected ID cannot have multiple governed entity types")
        object.__setattr__(
            self,
            "_impact_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def impact_sha256(self) -> str:
        return self._impact_sha256

    @property
    def identity_sha256(self) -> str:
        return self.impact_sha256

    @property
    def impact_id(self) -> str:
        return f"GOVERNANCE-IMPACT-{self.impact_sha256}"

    @property
    def has_unknown_impact(self) -> bool:
        return bool(self.unresolved_reference_ids or self.unknown_impact_ids)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "affected_capability_ids": list(self.affected_capability_ids),
            "affected_fact_ids": list(self.affected_fact_ids),
            "affected_generated_application_provenance_ids": list(
                self.affected_generated_application_provenance_ids
            ),
            "affected_rule_ids": list(self.affected_rule_ids),
            "affected_template_ids": list(self.affected_template_ids),
            "evidence_graph_digest": self.evidence_graph_digest,
            "freshness_source_identities": [
                {
                    "content_sha256": content_sha256,
                    "revision": revision,
                    "source_id": source_id,
                }
                for source_id, revision, content_sha256 in self.freshness_source_identities
            ],
            "reverse_transitive_ids": list(self.reverse_transitive_ids),
            "schema_version": self.schema_version,
            "semantic_diff_id": self.semantic_diff_id,
            "stale_evidence_ids": list(self.stale_evidence_ids),
            "unknown_impact_ids": list(self.unknown_impact_ids),
            "unresolved_reference_ids": list(self.unresolved_reference_ids),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "has_unknown_impact": self.has_unknown_impact,
            "impact_id": self.impact_id,
            "impact_sha256": self.impact_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def project_impact(
    semantic_diff: SemanticDiff,
    evidence_graph: EvidenceGraph | None = None,
    current_sources: Mapping[str, tuple[str, str]] | None = None,
) -> ImpactProjection:
    """Project deduplicated reverse impact without inventing graph entities.

    Edges are interpreted in dependency orientation: ``source_id`` depends on
    ``target_id``.  Therefore a changed/stale target affects sources discovered
    with M2.4 reverse traversal.  Callers must supply exact current source
    identities to request freshness propagation.
    """
    if not isinstance(semantic_diff, SemanticDiff):
        raise ImpactModelError("semantic_diff must be a SemanticDiff")
    if evidence_graph is not None and not isinstance(evidence_graph, EvidenceGraph):
        raise ImpactModelError("evidence_graph must be an M2.4 EvidenceGraph")
    if evidence_graph is None and current_sources is not None:
        raise ImpactModelError("freshness propagation requires an EvidenceGraph")

    normalized_sources = _normalize_current_sources(current_sources)
    freshness_map = {
        source_id: (revision, content_sha256)
        for source_id, revision, content_sha256 in normalized_sources
    }
    buckets = _type_buckets()
    changed_ids: set[str] = set()
    changed_types: dict[str, GovernedEntityType] = {}
    for change in semantic_diff.changes:
        buckets[change.entity_type].add(change.entity_id)
        changed_ids.add(change.entity_id)
        previous = changed_types.get(change.entity_id)
        if previous is not None and previous is not change.entity_type:
            raise ImpactModelError(
                f"governed entity ID is ambiguous across entity types: {change.entity_id}"
            )
        changed_types[change.entity_id] = change.entity_type

    graph_digest: str | None = None
    stale_ids: set[str] = set()
    transitive_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    unknown_ids: set[str] = set()
    if evidence_graph is None:
        # The changed entity is known, but downstream impact is not knowable
        # without caller-supplied relationship evidence.
        unresolved_ids.update(changed_ids)
        unknown_ids.update(changed_ids)
    else:
        graph_dict = evidence_graph.to_dict()
        graph_digest = cast(str, graph_dict["graph_digest"])
        graph_ids = set(evidence_graph.node_ids())
        unresolved_ids.update(changed_ids - graph_ids)
        unknown_ids.update(changed_ids - graph_ids)
        if current_sources is not None:
            stale_ids.update(evidence_graph.stale_nodes(freshness_map))

        roots = (changed_ids & graph_ids) | stale_ids
        for root_id in sorted(roots):
            transitive_ids.update(evidence_graph.traverse(root_id, reverse=True, transitive=True))
        projected_ids = roots | transitive_ids
        for node_id in sorted(projected_ids):
            if node_id in changed_types:
                buckets[changed_types[node_id]].add(node_id)
                continue
            node_type = evidence_graph.node(node_id).node_type
            entity_type = _GRAPH_NODE_TYPES.get(node_type)
            if entity_type is None:
                unknown_ids.add(node_id)
            else:
                buckets[entity_type].add(node_id)

    return ImpactProjection(
        semantic_diff_id=semantic_diff.diff_id,
        evidence_graph_digest=graph_digest,
        freshness_source_identities=normalized_sources,
        affected_fact_ids=tuple(buckets[GovernedEntityType.FACT]),
        affected_rule_ids=tuple(buckets[GovernedEntityType.RULE]),
        affected_capability_ids=tuple(buckets[GovernedEntityType.CAPABILITY]),
        affected_template_ids=tuple(buckets[GovernedEntityType.TEMPLATE]),
        affected_generated_application_provenance_ids=tuple(
            buckets[GovernedEntityType.GENERATED_APPLICATION_PROVENANCE]
        ),
        stale_evidence_ids=tuple(stale_ids),
        reverse_transitive_ids=tuple(transitive_ids),
        unresolved_reference_ids=tuple(unresolved_ids),
        unknown_impact_ids=tuple(unknown_ids),
    )


# Descriptive aliases retain one implementation and one identity contract.
ChangeClassification = SemanticChangeKind
GovernedEntityKind = GovernedEntityType
semantic_diff = diff_governance_snapshots
project_reverse_impact = project_impact
