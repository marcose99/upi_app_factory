from __future__ import annotations

import json
from pathlib import Path

from factory.application_engineering.deep_composer import DeepApplicationComposer
from factory.documentation import validate_portal_integrity


def test_deep_composer_emits_conditional_artifact_parity_evidence(tmp_path: Path) -> None:
    requirements = {
        "schema_version": "requirements-ir/v1",
        "traceability": [{"requirement_id": "REQ-1", "collection": "apis"}],
    }
    DeepApplicationComposer(Path.cwd()).compose(
        requirements_ir=requirements, output_root=tmp_path, app_id="parity_probe"
    )
    docs = tmp_path / "parity_probe/docs"
    portal = json.loads((docs / "index.json").read_text())
    assert validate_portal_integrity(portal, docs)["status"] == "PROVEN"
    paths = {entry["json_path"] for entry in portal["entries"]}
    assert paths >= {
        "evidence/artifact_parity.json", "evidence/dependency_inventory.json",
        "evidence/license_inventory.json", "evidence/sbom_cyclonedx.json",
        "evidence/build_source_provenance.json", "evidence/security_assurance.json",
        "evidence/test_assurance.json", "evidence/runtime_operations.json",
        "evidence/event_contract.json", "evidence/artifact_manifest.json",
        "evidence/api_contract.json", "evidence/configuration_inventory.json",
        "evidence/data_inventory.json",
    }
    event = json.loads((docs / "evidence/event_contract.json").read_text())
    assert event["applicability_status"] == "NOT_APPLICABLE"
    assert event["reason"] and event["asyncapi_path"] is None
    security = json.loads((docs / "evidence/security_assurance.json").read_text())
    assert security["vulnerability_scan_status"] == "NOT_YET_MEASURED"
    assert security["penetration_test_status"] == "PENDING_EXTERNAL_AUTHORITY"
    manifest = json.loads((docs / "evidence/artifact_manifest.json").read_text())
    assert manifest["artifacts"] and all(row["sha256"] for row in manifest["artifacts"])
