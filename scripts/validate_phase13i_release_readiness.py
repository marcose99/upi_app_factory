#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13I"
RUN_ID = "first_governed_generation_run_001"
BASELINE_TAG = "v0.13.7-release-state-lineage-registry"
ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13i"
    / "release_readiness_audit.json"
)
PORTAL_PATH = (
    ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "audit_portal"
    / "factory_release_readiness_operator_acceptance_portal.html"
)
DOCS = [
    ROOT / "docs" / "phase13i" / "release_readiness_policy.json",
    ROOT / "docs" / "phase13i" / "release_readiness_architecture.json",
    ROOT / "docs" / "phase13i" / "release_readiness_operator_acceptance.md",
]


def main() -> int:
    errors: list[str] = []
    if not AUDIT_PATH.exists():
        errors.append(f"Missing audit file: {AUDIT_PATH}")
    if not PORTAL_PATH.exists():
        errors.append(f"Missing portal file: {PORTAL_PATH}")
    for path in DOCS:
        if not path.exists():
            errors.append(f"Missing Phase 13I document: {path}")
    audit = {}
    if AUDIT_PATH.exists():
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        if audit.get("app_id") != APP_ID:
            errors.append("Unexpected app_id in release-readiness audit.")
        if audit.get("phase") != PHASE:
            errors.append("Unexpected phase in release-readiness audit.")
        if audit.get("run_id") != RUN_ID:
            errors.append("Unexpected run_id in release-readiness audit.")
        if audit.get("baseline_tag") != BASELINE_TAG:
            errors.append("Unexpected baseline tag in release-readiness audit.")
        if not audit.get("baseline_tag_present"):
            errors.append("Baseline tag is not present.")
        if not audit.get("passed"):
            errors.append("Release-readiness audit did not pass.")
        determinism = audit.get("evidence_determinism", {})
        if determinism.get("uses_current_commit_hash"):
            errors.append("Release-readiness evidence must not use current commit hash.")
        if determinism.get("uses_wall_clock_timestamp"):
            errors.append("Release-readiness evidence must not use wall-clock timestamp.")
        for item in audit.get("release_lineage", []):
            if not item.get("tag_present"):
                errors.append(f"Missing release lineage tag: {item.get('tag')}")
        for path, present in audit.get("required_files", {}).items():
            if not present:
                errors.append(f"Missing required file: {path}")
        for check in audit.get("operator_smoke_checks", []):
            if not check.get("passed"):
                errors.append(f"Operator smoke check failed: {check.get('command')}")
            if check.get("handover_missing_entries"):
                errors.append("factoryctl handover still reports missing entries.")
        truth_boundary = audit.get("truth_boundary", "")
        if "LangGraph/OpenAI" not in truth_boundary or "policy-gated" not in truth_boundary:
            errors.append("Truth boundary does not preserve LangGraph/OpenAI policy gating.")
    result = {
        "app_id": APP_ID,
        "baseline_tag": BASELINE_TAG,
        "errors": errors,
        "passed": not errors,
        "phase": PHASE,
        "run_id": RUN_ID,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
