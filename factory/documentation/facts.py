"""Canonical, provenance-bound fact and evidence graph.

The graph deliberately stores assertions as JSON data and source bindings, not prose-derived
authority.  Caller-supplied stable IDs identify repository concepts; deterministic edge IDs
identify relationships without depending on insertion or filesystem order.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, cast

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class FactModelError(ValueError):
    """Raised when governed fact data is invalid or inconsistent."""


class FactStatus(str, Enum):
    PROVEN = "PROVEN"
    PARTIAL = "PARTIAL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    UNKNOWN_EXPLICIT = "UNKNOWN_EXPLICIT"
    NOT_YET_MEASURED = "NOT_YET_MEASURED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING_EXTERNAL_AUTHORITY = "PENDING_EXTERNAL_AUTHORITY"
    NOT_RELEASED = "NOT_RELEASED"
    NOT_DEPLOYED = "NOT_DEPLOYED"


class Freshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"


def canonical_json(value: Any) -> str:
    """Return deterministic UTF-8 JSON text, rejecting non-JSON and non-finite values."""
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise FactModelError(f"value is not canonical JSON data: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_snapshot(value: Any) -> Any:
    """Detach governed data from caller-owned mutable objects."""
    return json.loads(canonical_json(value))


def _identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FactModelError(f"{field_name} must be a non-empty stable identifier")
    return value


@dataclass(frozen=True)
class ProvenanceBinding:
    """Immutable identity of the authoritative material supporting a fact."""

    source_id: str
    revision: str
    content_sha256: str
    source_type: str

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.revision, "revision")
        _identifier(self.source_type, "source_type")
        if not isinstance(self.content_sha256, str) or not _SHA256.fullmatch(
            self.content_sha256
        ):
            raise FactModelError("content_sha256 must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "content_sha256": self.content_sha256,
            "revision": self.revision,
            "source_id": self.source_id,
            "source_type": self.source_type,
        }

    def freshness_against(self, current: Mapping[str, tuple[str, str]]) -> Freshness:
        return (
            Freshness.CURRENT
            if current.get(self.source_id) == (self.revision, self.content_sha256)
            else Freshness.STALE
        )


@dataclass(frozen=True)
class FactNode:
    node_id: str
    node_type: str
    status: FactStatus
    value: Any = None
    provenance: tuple[ProvenanceBinding, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _identifier(self.node_id, "node_id")
        _identifier(self.node_type, "node_type")
        if not isinstance(self.status, FactStatus):
            raise FactModelError("status must use the explicit FactStatus vocabulary")
        if self.status is FactStatus.PROVEN and not self.provenance:
            raise FactModelError("PROVEN nodes require authoritative provenance")
        if self.status is not FactStatus.PROVEN and self.value is not None:
            raise FactModelError("non-PROVEN nodes cannot carry asserted values")
        object.__setattr__(self, "value", _canonical_snapshot(self.value))
        object.__setattr__(self, "metadata", _canonical_snapshot(dict(self.metadata)))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        source_ids = [binding.source_id for binding in self.provenance]
        if len(source_ids) != len(set(source_ids)):
            raise FactModelError("node provenance source IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], _canonical_snapshot({
            "metadata": dict(self.metadata),
            "node_id": self.node_id,
            "node_type": self.node_type,
            "provenance": [
                item.to_dict()
                for item in sorted(self.provenance, key=lambda x: x.source_id)
            ],
            "status": self.status.value,
            "value": self.value,
        }))

    def freshness(self, current: Mapping[str, tuple[str, str]]) -> Freshness:
        return (
            Freshness.CURRENT
            if self.provenance
            and all(
                item.freshness_against(current) is Freshness.CURRENT
                for item in self.provenance
            )
            else Freshness.STALE
        )


@dataclass(frozen=True)
class FactEdge:
    source_id: str
    relation: str
    target_id: str
    provenance_ids: tuple[str, ...]
    edge_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.relation, "relation")
        _identifier(self.target_id, "target_id")
        if isinstance(self.provenance_ids, str):
            raise FactModelError("edges require a collection of provenance identities")
        provenance_ids = tuple(self.provenance_ids)
        if not provenance_ids or any(
            not isinstance(item, str) or not item.strip() or item != item.strip()
            for item in provenance_ids
        ):
            raise FactModelError("edges require provenance-backed identities")
        if len(provenance_ids) != len(set(provenance_ids)):
            raise FactModelError("edge provenance IDs must be unique")
        object.__setattr__(self, "provenance_ids", provenance_ids)
        expected = "EDGE-" + canonical_sha256(self.identity_payload())[:24]
        if self.edge_id and self.edge_id != expected:
            raise FactModelError("edge_id does not match its canonical relationship identity")
        object.__setattr__(self, "edge_id", expected)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "provenance_ids": sorted(self.provenance_ids),
            "relation": self.relation,
            "source_id": self.source_id,
            "target_id": self.target_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, **self.identity_payload()}


class EvidenceGraph:
    """A deterministic directed graph supporting forward and reverse impact traversal."""

    schema_version = "upi_app_factory.fact-evidence-graph.v1"

    def __init__(self, nodes: Iterable[FactNode] = (), edges: Iterable[FactEdge] = ()) -> None:
        self._nodes: dict[str, FactNode] = {}
        self._edges: dict[str, FactEdge] = {}
        for node in nodes:
            self.add_node(node)
        for edge in edges:
            self.add_edge(edge)

    def add_node(self, node: FactNode) -> None:
        if node.node_id in self._nodes:
            raise FactModelError(f"duplicate node_id: {node.node_id}")
        self._nodes[node.node_id] = node

    def add_edge(self, edge: FactEdge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise FactModelError("edge endpoints must exist before the edge is added")
        known_sources = {
            binding.source_id
            for endpoint in (self._nodes[edge.source_id], self._nodes[edge.target_id])
            for binding in endpoint.provenance
        }
        if not set(edge.provenance_ids).issubset(known_sources):
            raise FactModelError("edge provenance must resolve in an endpoint node")
        if edge.edge_id in self._edges:
            raise FactModelError(f"duplicate edge_id: {edge.edge_id}")
        self._edges[edge.edge_id] = edge

    def node(self, node_id: str) -> FactNode:
        """Return a node by stable ID without exposing the mutable graph index."""
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise FactModelError(f"unknown node_id: {node_id}") from exc

    def node_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._nodes))

    def traverse(
        self, node_id: str, *, reverse: bool = False, transitive: bool = True
    ) -> tuple[str, ...]:
        if node_id not in self._nodes:
            raise FactModelError(f"unknown node_id: {node_id}")
        visited: set[str] = set()
        frontier = [node_id]
        while frontier:
            current = frontier.pop(0)
            adjacent = sorted(
                edge.source_id if reverse else edge.target_id
                for edge in self._edges.values()
                if (edge.target_id if reverse else edge.source_id) == current
            )
            for item in adjacent:
                if item != node_id and item not in visited:
                    visited.add(item)
                    if transitive:
                        frontier.append(item)
        return tuple(sorted(visited))

    def stale_nodes(self, current: Mapping[str, tuple[str, str]]) -> tuple[str, ...]:
        return tuple(
            sorted(
                node_id
                for node_id, node in self._nodes.items()
                if node.freshness(current) is Freshness.STALE
            )
        )

    def to_dict(self) -> dict[str, Any]:
        body = {
            "edges": [self._edges[key].to_dict() for key in sorted(self._edges)],
            "nodes": [self._nodes[key].to_dict() for key in sorted(self._nodes)],
            "schema_version": self.schema_version,
        }
        return {**body, "graph_digest": canonical_sha256(body)}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())
