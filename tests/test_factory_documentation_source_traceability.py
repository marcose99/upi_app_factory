from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_documentation_manifest_traces_sources_and_controls() -> None:
    manifest = json.loads((PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "upi-app-factory.factory-documentation.v1"
    assert manifest["controls_traced"] >= 34
    assert manifest["routes_traced"] >= 34
    sources = {item["path"]: item["sha256"] for item in manifest["source_traceability"]}
    for path in [
        "factory/operator_portal/local_web_api.py",
        "factory/operator_portal/web_ui/static/index.html",
        "scripts/build_factory_complete_documentation.py",
        "config/factory_runtime.env.example",
    ]:
        assert path in sources
        assert len(sources[path]) == 64
