#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13K"
BASELINE_TAG = "v0.13.9-release-handoff-bundle-pack"
ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13k" / "release_handoff_replay_audit.json"
PORTAL_FILE = ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_release_handoff_replay_verification_portal.html"


def main() -> int:
    errors: list[str] = []
    if not AUDIT_FILE.exists():
        errors.append(f"Missing audit file: {AUDIT_FILE.relative_to(ROOT)}")
        data = {}
    else:
        data = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))

    if data.get("phase") != PHASE:
        errors.append("Audit phase mismatch")
    if data.get("baseline_tag") != BASELINE_TAG:
        errors.append("Baseline tag mismatch")
    if not data.get("baseline_tag_present"):
        errors.append("Baseline tag not present")
    if data.get("checksum_scope") != "repository_root":
        errors.append("Checksum scope must be repository_root")
    if data.get("determinism_policy", {}).get("uses_wall_clock_timestamp") is not False:
        errors.append("Replay audit must not use wall-clock timestamp")
    if data.get("determinism_policy", {}).get("uses_current_commit_hash") is not False:
        errors.append("Replay audit must not use current commit hash")
    if data.get("errors"):
        errors.extend(str(error) for error in data.get("errors", []))
    if not data.get("passed"):
        errors.append("Replay audit did not pass")

    checksums = data.get("checksum_entries", [])
    if not checksums:
        errors.append("No checksum entries verified")
    for item in checksums:
        if item.get("scope") != "repository_root":
            errors.append(f"Checksum entry has wrong scope: {item.get('path')}")
        if not item.get("exists") or not item.get("matches"):
            errors.append(f"Checksum entry failed: {item.get('path')}")

    for item in data.get("operator_smoke_checks", []):
        if not item.get("passed"):
            errors.append(f"Operator smoke check failed: {item.get('command')}")
        if item.get("contains_missing_marker"):
            errors.append(f"Operator smoke check found [MISSING]: {item.get('command')}")

    truth_checks = data.get("truth_boundary_checks", {})
    for key in ["mentions_local_deterministic", "mentions_langgraph_openai_policy_gate", "mentions_not_falsely_claimed"]:
        if truth_checks.get(key) is not True:
            errors.append(f"Truth boundary check failed: {key}")

    if not PORTAL_FILE.exists():
        errors.append(f"Missing portal file: {PORTAL_FILE.relative_to(ROOT)}")

    result = {
        "phase": PHASE,
        "app_id": APP_ID,
        "baseline_tag": BASELINE_TAG,
        "errors": errors,
        "passed": not errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
