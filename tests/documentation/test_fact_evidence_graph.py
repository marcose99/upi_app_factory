import json

import pytest

from factory.documentation import (
    EvidenceGraph,
    FactEdge,
    FactNode,
    FactStatus,
    Freshness,
    ProvenanceBinding,
    canonical_sha256,
)
from factory.documentation.facts import FactModelError


def binding(source_id: str, revision: str = "git:abc") -> ProvenanceBinding:
    return ProvenanceBinding(
        source_id, revision, canonical_sha256({"source": source_id}), "SOURCE_CODE"
    )


def test_graph_has_stable_identity_canonical_serialization_and_reverse_traversal() -> None:
    requirement = FactNode(
        "REQ-001", "SOURCE_REQUIREMENT", FactStatus.PROVEN,
        {"shall": "work"}, (binding("SRC-REQ"),),
    )
    implementation = FactNode(
        "IMPL-api", "SOURCE_SYMBOL", FactStatus.PROVEN,
        "factory.api:handle", (binding("SRC-IMPL"),),
    )
    test = FactNode(
        "TEST-api", "TEST", FactStatus.PROVEN,
        {"result": "passed"}, (binding("SRC-TEST"),),
    )
    edges = (
        FactEdge("REQ-001", "IMPLEMENTED_BY", "IMPL-api", ("SRC-REQ", "SRC-IMPL")),
        FactEdge("IMPL-api", "VERIFIED_BY", "TEST-api", ("SRC-IMPL", "SRC-TEST")),
    )
    graph = EvidenceGraph((test, requirement, implementation), reversed(edges))

    assert graph.traverse("REQ-001") == ("IMPL-api", "TEST-api")
    assert graph.traverse("TEST-api", reverse=True) == ("IMPL-api", "REQ-001")
    assert graph.to_json() == graph.to_json()
    assert json.loads(graph.to_json())["nodes"][0]["node_id"] == "IMPL-api"


def test_freshness_binds_both_revision_and_content_identity() -> None:
    source = binding("SRC-1")
    node = FactNode("FACT-1", "CONFIGURATION", FactStatus.PROVEN, {"enabled": True}, (source,))
    assert node.freshness({"SRC-1": (source.revision, source.content_sha256)}) is Freshness.CURRENT
    assert node.freshness({"SRC-1": ("git:different", source.content_sha256)}) is Freshness.STALE
    assert node.freshness({"SRC-1": (source.revision, "0" * 64)}) is Freshness.STALE


def test_proven_status_and_edges_fail_closed_without_provenance() -> None:
    with pytest.raises(FactModelError, match="PROVEN nodes require"):
        FactNode("FACT-1", "CLAIM", FactStatus.PROVEN, True)
    unknown = FactNode("FACT-2", "CLAIM", FactStatus.UNKNOWN_EXPLICIT)
    graph = EvidenceGraph((unknown,))
    with pytest.raises(FactModelError, match="endpoints"):
        graph.add_edge(FactEdge("FACT-2", "REALIZED_AS", "missing", ("SRC-1",)))


def test_non_proven_status_cannot_smuggle_an_asserted_value() -> None:
    with pytest.raises(FactModelError, match="cannot carry asserted"):
        FactNode("METRIC-1", "MEASUREMENT", FactStatus.NOT_YET_MEASURED, 99)


def test_node_canonical_data_is_detached_from_mutable_caller_input() -> None:
    value = {"items": ["original"]}
    metadata = {"owner": {"id": "team-1"}}
    node = FactNode("FACT-1", "CONFIGURATION", FactStatus.PROVEN, value, (binding("SRC-1"),), metadata)
    before = node.to_dict()

    value["items"].append("mutated")
    metadata["owner"]["id"] = "changed"

    assert node.to_dict() == before
    projected = node.to_dict()
    projected["value"]["items"].append("projection mutation")
    assert node.to_dict() == before


def test_edge_identity_is_detached_from_mutable_caller_input() -> None:
    provenance_ids = ["SRC-1", "SRC-2"]
    edge = FactEdge("FACT-1", "REALIZED_AS", "FACT-2", provenance_ids)  # type: ignore[arg-type]
    before = edge.to_dict()

    provenance_ids.append("SRC-MUTATED")

    assert edge.to_dict() == before
    assert edge.provenance_ids == ("SRC-1", "SRC-2")
