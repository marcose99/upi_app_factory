#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
PHASE = "Phase 13H"
BASELINE_TAG = "v0.13.6-readonly-validation-drift-guardrails"
SNAPSHOT = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13h" / "release_state_snapshot.json"
PORTAL = ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_release_state_lineage_portal.html"
POLICY = ROOT / "docs" / "phase13h" / "release_state_lineage_policy.json"


def contains_forbidden_volatile_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in {"generated_at", "timestamp", "current_commit", "head_commit", "commit_hash"}:
                return True
            if contains_forbidden_volatile_key(child):
                return True
    if isinstance(value, list):
        return any(contains_forbidden_volatile_key(item) for item in value)
    return False


def git_tag_present(tag: str) -> bool:
    result = subprocess.run(["git", "tag", "--list", tag], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return tag in result.stdout.splitlines()


def main() -> int:
    errors: list[str] = []
    for path in [SNAPSHOT, PORTAL, POLICY]:
        if not path.exists():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")
    payload: dict[str, Any] = {}
    if SNAPSHOT.exists():
        payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        if payload.get("phase") != PHASE:
            errors.append("Snapshot phase mismatch.")
        if payload.get("app_id") != APP_ID:
            errors.append("Snapshot app_id mismatch.")
        if payload.get("run_id") != RUN_ID:
            errors.append("Snapshot run_id mismatch.")
        if payload.get("baseline_tag") != BASELINE_TAG:
            errors.append("Baseline tag mismatch.")
        if payload.get("baseline_tag_present") is not True:
            errors.append("Baseline tag is not marked present in snapshot.")
        if not git_tag_present(BASELINE_TAG):
            errors.append("Baseline tag is not present in local git tags.")
        if contains_forbidden_volatile_key(payload):
            errors.append("Snapshot contains volatile timestamp or commit-hash keys.")
        if payload.get("evidence_determinism", {}).get("uses_wall_clock_timestamp") is not False:
            errors.append("Snapshot must explicitly avoid wall-clock timestamps.")
        if payload.get("evidence_determinism", {}).get("uses_current_commit_hash") is not False:
            errors.append("Snapshot must explicitly avoid current commit hashes.")
        if not payload.get("release_lineage"):
            errors.append("Release lineage is empty.")
        missing_files = [path for path, present in payload.get("required_files", {}).items() if not present]
        if missing_files:
            errors.append("Missing required release-state files: " + ", ".join(missing_files))
        missing_tags = [item.get("tag") for item in payload.get("release_lineage", []) if not item.get("tag_present")]
        if missing_tags:
            errors.append("Missing lineage tags: " + ", ".join(str(tag) for tag in missing_tags))
    result = {
        "phase": PHASE,
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "baseline_tag": BASELINE_TAG,
        "errors": errors,
        "passed": not errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
