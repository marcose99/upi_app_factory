#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DOCS = ROOT / "docs" / "phase12a"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase12a"
PORTAL = ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "human_validator_audit_portal.html"

REQUIRED_FILES = [
    "audit_charter.md",
    "audit_control_catalog.json",
    "audit_scorecard_schema.json",
    "factory_audit_scorecard.md",
    "agentic_ai_safety_audit_scorecard.md",
    "upi_domain_audit_scorecard.md",
    "architecture_design_audit_scorecard.md",
    "test_quality_audit_scorecard.md",
    "security_privacy_audit_scorecard.md",
    "observability_audit_scorecard.md",
    "business_value_audit_scorecard.md",
    "audit_evidence_manifest.json",
    "pre_generation_audit_report.md",
    "html_human_validator_portal_contract.md",
    "html_human_validator_portal_contract.json",
    "generated_application_post_generation_audit_plan.json",
]

REQUIRED_TERMS = {
    "audit_charter.md": ["factory governance", "agentic AI safety", "UPI domain guardrails", "business value"],
    "audit_control_catalog.json": ["factory_governance", "agentic_ai_safety", "human_validator_portal"],
    "audit_scorecard_schema.json": ["score_scale", "evidence_paths", "recommendations"],
    "html_human_validator_portal_contract.md": ["offline", "animated diagrams", "traceability", "human validator"],
    "html_human_validator_portal_contract.json": ["human_validator_audit_portal.html", "animated_diagrams", "must_not_claim"],
    "generated_application_post_generation_audit_plan.json": ["post_generation_audit", "generated app requirements traceability", "human validator portal publication"],
    "pre_generation_audit_report.md": ["PRE-GENERATION AUDIT FRAMEWORK READY", "post-generation audit"],
}


def _check_root(root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for name in REQUIRED_FILES:
        path = root / name
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})
            continue
        text = path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS.get(name, []):
            if term not in text:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"missing_term:{term}"})
    return errors


def validate() -> dict[str, Any]:
    errors = _check_root(DOCS) + _check_root(WORKSPACE)
    if not PORTAL.exists():
        errors.append({"path": str(PORTAL.relative_to(ROOT)), "error": "missing_portal_html"})
    else:
        portal = PORTAL.read_text(encoding="utf-8")
        for term in [
            "FactoryFromNothing",
            "Animated Agentic Factory Flow",
            "Animated Generated UPI Application Data Flow",
            "Human Validator Checklist",
            "must not claim regulatory compliance",
        ]:
            if term not in portal:
                errors.append({"path": str(PORTAL.relative_to(ROOT)), "error": f"missing_portal_term:{term}"})
    return {
        "passed": not errors,
        "phase": "Phase 12A",
        "app_id": APP_ID,
        "docs_files_checked": len(REQUIRED_FILES),
        "workspace_files_checked": len(REQUIRED_FILES),
        "portal_checked": PORTAL.exists(),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
