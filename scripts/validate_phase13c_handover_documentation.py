#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_current_operational_contract import validate as validate_current  # noqa: E402

APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
FACTORY_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DOCS = ROOT / "docs" / "phase13c"
MANIFEST = PHASE_DOCS / "handover_deployment_documentation_manifest.json"


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not MANIFEST.exists():
        errors.append({"path": str(MANIFEST.relative_to(ROOT)), "error": "missing_manifest"})
        return {"passed": False, "errors": errors}

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    listed_files = manifest["handover_docs"] + manifest["deployment_guides"] + manifest["runbooks"]

    for rel in listed_files:
        path = ROOT / rel
        if not path.exists():
            errors.append({"path": rel, "error": "missing_document"})

    for root in [
        PHASE_DOCS,
        FACTORY_ROOT / "lifecycle_artifacts" / "phase13c",
        FACTORY_ROOT / "generation_runs" / RUN_ID,
    ]:
        artifact = root / "handover_deployment_documentation_manifest.json"
        if not artifact.exists():
            errors.append(
                {
                    "path": str(artifact.relative_to(ROOT)),
                    "error": "missing_mirrored_manifest",
                }
            )

    current = validate_current()
    if not current["passed"]:
        for error in current["errors"]:
            errors.append(
                {
                    "path": "factory_governance/current_contracts",
                    "error": f"current_contract:{error}",
                }
            )

    return {
        "passed": not errors,
        "phase": "Phase 13C",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "documents_checked": len(listed_files),
        "compatibility_mode": "legacy_phase_provenance_plus_generic_upi_contract_delegation",
        "current_contract_schema": current.get("generic_contract_schema"),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
