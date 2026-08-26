"""Deterministic traceability projections and documentation portals.

JSON is authoritative.  HTML is an offline, escaped projection which binds to the
SHA-256 of the exact JSON bytes written beside it.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .facts import EvidenceGraph, FactModelError, canonical_json, canonical_sha256

DOCUMENT_SCHEMA = "upi_app_factory.governed-document.v1"
PORTAL_SCHEMA = "upi_app_factory.documentation-portal.v1"

_VIEWS: dict[str, tuple[str, ...]] = {
    "feature_capability_catalogue": ("REALIZED_AS",),
    "requirements_disposition": ("NORMALIZED_AS", "REALIZED_AS"),
    "implementation_traceability": ("IMPLEMENTED_BY",),
    "test_traceability": ("VERIFIED_BY",),
    "architecture_traceability": ("ARCHITECTED_BY",),
    "security_traceability": ("SECURITY_CONTROL_FOR", "VERIFIED_BY"),
    "data_traceability": ("CLASSIFIES", "LINEAGE_FROM"),
    "configuration_traceability": ("CONFIGURES", "DEPENDS_ON"),
    "requirements_to_release_traceability": ("INCLUDED_IN", "RELEASED_IN"),
    "release_to_requirements_traceability": ("INCLUDED_IN", "RELEASED_IN"),
    "change_impact_matrix": (),
}


def _document(document_id: str, subject_id: str, source_fact_ids: Iterable[str],
              body: Mapping[str, Any], *, status: str = "PROVEN") -> dict[str, Any]:
    core = {
        "applicability_status": status,
        "document_id": document_id,
        "generated_at": "DETERMINISTIC_FROM_SOURCE_FACT_IDENTITIES",
        "schema_version": DOCUMENT_SCHEMA,
        "source_fact_ids": sorted(set(source_fact_ids)),
        "subject_id": subject_id,
        **dict(body),
    }
    return {**core, "document_digest": canonical_sha256(core)}


def build_traceability_documents(graph: EvidenceGraph, subject_id: str) -> dict[str, dict[str, Any]]:
    """Derive stable report-specific views without introducing prose facts."""
    raw = graph.to_dict()
    nodes = {node["node_id"]: node for node in raw["nodes"]}
    edges = raw["edges"]
    result: dict[str, dict[str, Any]] = {}
    for view, relations in _VIEWS.items():
        if view == "change_impact_matrix":
            rows = [
                {"fact_id": node_id, "affected_fact_ids": list(graph.traverse(node_id))}
                for node_id in sorted(nodes)
                if nodes[node_id]["node_type"] in {"CHANGE", "DEFECT", "INCIDENT", "VULNERABILITY"}
            ]
        else:
            selected = [edge for edge in edges if edge["relation"] in relations]
            if view == "release_to_requirements_traceability":
                selected = [
                    {**edge, "source_id": edge["target_id"], "target_id": edge["source_id"]}
                    for edge in selected
                ]
            rows = selected
        fact_ids = sorted({item for row in rows for item in (row.get("source_id"), row.get("target_id")) if item})
        # Catalogue remains useful even where capability nodes have no relationship yet.
        if view == "feature_capability_catalogue":
            catalogue = [nodes[key] for key in sorted(nodes) if nodes[key]["node_type"] in {"FEATURE", "CAPABILITY", "FACTORY_CAPABILITY", "APPLICATION_FEATURE"}]
            fact_ids = sorted(set(fact_ids).union(item["node_id"] for item in catalogue))
            body: dict[str, Any] = {"entries": catalogue, "relationships": rows}
        else:
            body = {"entries": rows}
        result[view] = _document(f"DOC-{subject_id}-{view}", subject_id, fact_ids, body)
    return result


def render_document_html(document: Mapping[str, Any], json_sha256: str) -> str:
    """Render an accessible offline HTML projection bound to exact JSON bytes."""
    if len(json_sha256) != 64:
        raise FactModelError("json_sha256 must identify the exact canonical JSON artifact")
    title = html.escape(str(document.get("document_id", "Governed document")))
    payload = html.escape(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False))
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"json-sha256\" content=\"{json_sha256}\">"
        f"<title>{title}</title></head><body><main><h1>{title}</h1>"
        f"<p>Canonical JSON SHA-256: <code>{json_sha256}</code></p>"
        f"<pre>{payload}</pre></main></body></html>\n"
    )


def write_document_pair(root: Path, relative_stem: str, document: Mapping[str, Any]) -> dict[str, str]:
    json_path = root / f"{relative_stem}.json"
    html_path = root / f"{relative_stem}.html"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(document) + "\n").encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    json_path.write_bytes(encoded)
    html_path.write_text(render_document_html(document, digest), encoding="utf-8")
    return {"json": json_path.as_posix(), "html": html_path.as_posix(), "json_sha256": digest}


def build_portal(subject_id: str, entries: Iterable[Mapping[str, Any]], *,
                 source_fact_ids: Iterable[str] = (), status: str = "PROVEN") -> dict[str, Any]:
    normalized = sorted((dict(item) for item in entries), key=lambda item: (str(item.get("document_id")), str(item.get("json_path"))))
    core = {
        "applicability_status": status,
        "document_id": f"DOC-{subject_id}-index",
        "entries": normalized,
        "generated_at": "DETERMINISTIC_FROM_SOURCE_FACT_IDENTITIES",
        "known_limitations": [],
        "schema_version": PORTAL_SCHEMA,
        "source_fact_ids": sorted(set(source_fact_ids)),
        "subject_id": subject_id,
    }
    return {**core, "document_digest": canonical_sha256(core)}


def validate_portal_integrity(portal: Mapping[str, Any], docs_root: Path) -> dict[str, Any]:
    """Detect unsafe/broken links, duplicate IDs, orphan pairs, and stale digests."""
    errors: list[str] = []
    entries = portal.get("entries", [])
    if not isinstance(entries, list):
        raise FactModelError("portal entries must be a list")
    ids = [
        document_id
        for item in entries
        if isinstance(item, Mapping)
        for document_id in [item.get("document_id")]
        if isinstance(document_id, str)
    ]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    errors.extend(f"duplicate document_id: {item}" for item in duplicates)
    referenced: set[str] = {"index.json", "index.html"}
    for item in entries:
        if not isinstance(item, Mapping):
            errors.append("invalid portal entry")
            continue
        for field in ("json_path", "html_path"):
            value = item.get(field)
            if not isinstance(value, str) or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
                errors.append(f"unsafe {field}: {value}")
                continue
            referenced.add(value)
            if not (docs_root / value).is_file():
                errors.append(f"broken link: {value}")
        json_value = item.get("json_path")
        if isinstance(json_value, str) and (docs_root / json_value).is_file():
            actual = hashlib.sha256((docs_root / json_value).read_bytes()).hexdigest()
            if actual != item.get("json_sha256"):
                errors.append(f"stale digest: {json_value}")
    governed: set[str] = set()
    for path in docs_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(docs_root).as_posix()
        if path.suffix == ".json":
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(candidate, Mapping) and str(candidate.get("schema_version", "")).startswith("upi_app_factory."):
                governed.add(relative)
        elif path.suffix == ".html" and 'name="json-sha256"' in path.read_text(encoding="utf-8"):
            governed.add(relative)
    errors.extend(f"orphan artifact: {item}" for item in sorted(governed - referenced))
    return {"gate": "DOCUMENTATION_PORTAL_INTEGRITY_GATE", "status": "PROVEN" if not errors else "FAIL", "errors": sorted(errors)}
