"""Fact-derived documentation primitives."""

from .facts import (
    EvidenceGraph,
    FactEdge,
    FactNode,
    FactStatus,
    Freshness,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from .factuality import Claim, FactualityError, validate_factuality
from .traceability import (
    build_portal,
    build_traceability_documents,
    render_document_html,
    validate_portal_integrity,
    write_document_pair,
)

__all__ = [
    "Claim",
    "EvidenceGraph",
    "FactEdge",
    "FactNode",
    "FactStatus",
    "FactualityError",
    "Freshness",
    "ProvenanceBinding",
    "canonical_json",
    "canonical_sha256",
    "validate_factuality",
    "build_portal",
    "build_traceability_documents",
    "render_document_html",
    "validate_portal_integrity",
    "write_document_pair",
]
