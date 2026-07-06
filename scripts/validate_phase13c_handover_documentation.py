#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
FACTORY_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DOCS = ROOT / "docs" / "phase13c"
MANIFEST = PHASE_DOCS / "handover_deployment_documentation_manifest.json"


REQUIRED_TERMS = {
    "docs/handover/README_HANDOVER.md": [
        "Factory Handover Guide",
        "Truth boundary",
        "Primary generated application",
        "External ecosystem",
    ],
    "docs/handover/QUICKSTART.md": ["Quickstart", "git checkout", "Validate baseline"],
    "docs/handover/COMMAND_REFERENCE.md": ["./factory doctor", "./factory generate", "Current script equivalents"],
    "docs/handover/GOVERNANCE_AUDIT_SELF_CORRECTION_GUIDE.md": ["Every warning and error", "Human approval required", "Blocked"],
    "docs/handover/PORTAL_GUIDE.md": ["Portal Guide", "Charts and visuals", "self-correction"],
    "docs/deployment/DEPLOYMENT_BOUNDARIES_AND_NON_CLAIMS.md": ["no live payment rail integration", "no real customer data"],
    "docs/runbooks/factory_handover_runbook.md": ["Factory Handover Runbook", "Exit criteria"],
    "docs/runbooks/handover_validation_runbook.md": ["Required gates", "no untriaged warnings/errors"],
    "docs/runbooks/generated_app_regeneration_runbook.md": ["Generated App Regeneration Runbook", "Only the generated application workspace"],
}


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not MANIFEST.exists():
        errors.append({"path": str(MANIFEST.relative_to(ROOT)), "error": "missing_manifest"})
        return {"passed": False, "errors": errors}

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    listed_files = (
        manifest["handover_docs"]
        + manifest["deployment_guides"]
        + manifest["runbooks"]
    )

    for rel in listed_files:
        path = ROOT / rel
        if not path.exists():
            errors.append({"path": rel, "error": "missing_document"})

    for rel, terms in REQUIRED_TERMS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for term in terms:
            if term not in text:
                errors.append({"path": rel, "error": f"missing_term:{term}"})

    for root in [
        PHASE_DOCS,
        FACTORY_ROOT / "lifecycle_artifacts" / "phase13c",
        FACTORY_ROOT / "generation_runs" / RUN_ID,
    ]:
        artifact = root / "handover_deployment_documentation_manifest.json"
        if not artifact.exists():
            errors.append({"path": str(artifact.relative_to(ROOT)), "error": "missing_mirrored_manifest"})

    return {
        "passed": not errors,
        "phase": "Phase 13C",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "documents_checked": len(listed_files),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
