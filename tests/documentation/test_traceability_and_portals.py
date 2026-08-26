from __future__ import annotations

import json
from pathlib import Path

from factory.documentation import (
    EvidenceGraph, FactEdge, FactNode, FactStatus, ProvenanceBinding,
    build_portal, build_traceability_documents, canonical_sha256,
    validate_portal_integrity, write_document_pair,
)


def _binding(source: str) -> ProvenanceBinding:
    return ProvenanceBinding(source, "git:tree-1", canonical_sha256(source), "SOURCE_CODE")


def _graph() -> EvidenceGraph:
    nodes = [
        FactNode("REQ-1", "SOURCE_REQUIREMENT", FactStatus.PROVEN, {"shall": "submit"}, (_binding("SRC-REQ"),)),
        FactNode("FEATURE-1", "APPLICATION_FEATURE", FactStatus.PROVEN, {"name": "submission"}, (_binding("SRC-FEATURE"),)),
        FactNode("IMPL-1", "SOURCE_SYMBOL", FactStatus.PROVEN, {"module": "app.api", "symbol": "submit"}, (_binding("SRC-IMPL"),)),
        FactNode("TEST-1", "TEST", FactStatus.PROVEN, {"nodeid": "tests/test_api.py::test_submit"}, (_binding("SRC-TEST"),)),
        FactNode("REL-1", "RELEASE", FactStatus.NOT_RELEASED),
    ]
    edges = [
        FactEdge("REQ-1", "REALIZED_AS", "FEATURE-1", ("SRC-REQ", "SRC-FEATURE")),
        FactEdge("FEATURE-1", "IMPLEMENTED_BY", "IMPL-1", ("SRC-FEATURE", "SRC-IMPL")),
        FactEdge("IMPL-1", "VERIFIED_BY", "TEST-1", ("SRC-IMPL", "SRC-TEST")),
    ]
    return EvidenceGraph(nodes, edges)


def test_report_specific_traceability_and_reverse_impact_are_deterministic() -> None:
    views = build_traceability_documents(_graph(), "upi_app_factory")
    assert set(views) >= {"feature_capability_catalogue", "requirements_disposition", "implementation_traceability", "test_traceability", "architecture_traceability", "security_traceability", "data_traceability", "configuration_traceability", "requirements_to_release_traceability", "release_to_requirements_traceability", "change_impact_matrix"}
    assert views["feature_capability_catalogue"]["entries"][0]["node_id"] == "FEATURE-1"
    assert views["implementation_traceability"]["entries"][0]["relation"] == "IMPLEMENTED_BY"
    assert views["test_traceability"]["entries"][0]["relation"] == "VERIFIED_BY"
    assert views["implementation_traceability"] != views["test_traceability"]


def test_portal_binds_exact_json_and_detects_broken_orphan_duplicate_and_stale(tmp_path: Path) -> None:
    document = build_traceability_documents(_graph(), "factory")["implementation_traceability"]
    result = write_document_pair(tmp_path, "implementation_traceability", document)
    portal = build_portal("factory", [{"document_id": document["document_id"], "json_path": "implementation_traceability.json", "html_path": "implementation_traceability.html", "json_sha256": result["json_sha256"]}])
    write_document_pair(tmp_path, "index", portal)
    assert validate_portal_integrity(portal, tmp_path)["status"] == "PROVEN"
    assert result["json_sha256"] in (tmp_path / "implementation_traceability.html").read_text()
    parsed = json.loads((tmp_path / "implementation_traceability.json").read_text())
    assert parsed["document_digest"] == document["document_digest"]

    (tmp_path / "implementation_traceability.json").write_text("{}\n")
    assert "stale digest" in " ".join(validate_portal_integrity(portal, tmp_path)["errors"])

