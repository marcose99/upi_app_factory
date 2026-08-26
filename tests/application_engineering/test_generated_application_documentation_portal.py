from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.application_engineering.deep_composer import DeepApplicationComposer
from factory.documentation import validate_portal_integrity


def test_generated_application_has_self_contained_provenance_capsule_and_portal(tmp_path: Path) -> None:
    requirements = {
        "schema_version": "requirements-ir/v1",
        "source_documents": [{"source_id": "REQ-SOURCE", "sha256": "a" * 64}],
        "traceability": [{"requirement_id": "REQ-1", "collection": "apis", "source": "REQ-SOURCE", "canonical_hash": "b" * 64}],
    }
    DeepApplicationComposer(Path.cwd()).compose(requirements_ir=requirements, output_root=tmp_path, app_id="portal_probe")
    docs = tmp_path / "portal_probe/docs"
    portal = json.loads((docs / "index.json").read_text())
    assert (docs / "index.html").is_file()
    assert validate_portal_integrity(portal, docs)["status"] == "PROVEN"
    names = {entry["json_path"] for entry in portal["entries"]}
    assert names >= {"requirements/requirements_ir.json", "requirements/requirements_traceability.json", "requirements/requirements_disposition.json", "requirements/requirements_provenance.json"}
    for entry in portal["entries"]:
        assert hashlib.sha256((docs / entry["json_path"]).read_bytes()).hexdigest() == entry["json_sha256"]
        assert entry["json_sha256"] in (docs / entry["html_path"]).read_text()
    release = json.loads((docs / "requirements/requirements_to_release_traceability.json").read_text())
    assert release["applicability_status"] == "NOT_RELEASED"
    trace = json.loads((docs / "requirements/requirements_traceability.json").read_text())
    assert trace["mappings"][0]["implementation_references"] == [
        {"module_path": "app/portal_probe/interfaces/api/main.py", "symbol": "app"}
    ]
