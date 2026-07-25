from __future__ import annotations

import json
from pathlib import Path
from pathlib import PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_documentation_manifest_traces_sources_and_controls() -> None:
    manifest = json.loads((PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "upi-app-factory.factory-documentation.v1"
    assert manifest["generated_at_utc"] == "1970-01-01T00:00:00Z"
    assert manifest["unresolved_claims"] == []
    assert manifest["controls_traced"] >= 34
    assert manifest["routes_traced"] >= 34
    assert manifest["technical_inventory"]["verified_claims_ingested"] >= 80
    assert manifest["technical_inventory"]["source_route_declarations"] >= 60
    assert manifest["technical_inventory"]["source_ui_controls"] >= 37
    assert len(manifest["animations"]) >= 4
    assert len(manifest["diagrams"]) >= 8
    sources = {item["path"]: item["sha256"] for item in manifest["source_files"]}
    assert {item["source_kind"] for item in manifest["source_files"]} == {"tracked_file"}
    for path in [
        "factory/operator_portal/local_web_api.py",
        "factory/operator_portal/web_ui/static/index.html",
        "scripts/build_factory_complete_documentation.py",
        "config/factory_runtime.env.example",
    ]:
        assert path in sources
        assert len(sources[path]) == 64
    assert sources == {item["path"]: item["sha256"] for item in manifest["source_traceability"]}
    assert {item["source_kind"] for item in manifest["source_traceability"]} == {"tracked_file"}
    source_facts = manifest["source_fact_inventory"]
    source_routes = {(item["method"], item["route"]) for item in source_facts["route_declarations"]}
    source_controls = set(source_facts["ui_controls"])
    assert ("GET", "/operator-portal/api/documentation/factory") in source_routes
    assert ("GET", "/operator-portal/api/runtime/runs/{run_id}/openapi") in source_routes
    assert "view-factory-documentation" in source_controls
    assert "download-factory-documentation" in source_controls


def test_documentation_manifest_traces_material_claim_evidence() -> None:
    manifest = json.loads((PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(encoding="utf-8"))
    claims = {item["claim_id"]: item for item in manifest["claim_evidence"]}
    for claim_id in [
        "requirements-ir",
        "portal-boundaries",
        "runtime-api",
        "generated-app-api",
        "GR-001",
        "C10",
    ]:
        claim = claims[claim_id]
        assert claim["section"]
        assert claim["statement"]
        assert claim["sources"]
        for source in claim["sources"]:
            assert source["path"]
            assert source["source_kind"] == "tracked_file"
            assert len(source["sha256"]) == 64
            assert source["locator"]
            assert source["observation"]
            assert not source["path"].startswith(".v5")
            assert not PurePosixPath(source["path"]).is_absolute()
