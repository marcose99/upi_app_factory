#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase26"
REQUIRED_FILES = [
    Path("docs/phase26/v1_release_candidate_consolidation.md"),
    Path("policies/phase26_v1_release_candidate_policy.json"),
    Path("scripts/run_phase26_v1_release_candidate_consolidation.py"),
    Path("scripts/validate_phase26_v1_release_candidate_consolidation.py"),
    Path("tests/test_phase26_v1_release_candidate_consolidation.py"),
    ARTIFACT_DIR / "v1_release_candidate_consolidation_audit.json",
    ARTIFACT_DIR / "v1_evidence_index.json",
    ARTIFACT_DIR / "v1_gap_register.json",
    ARTIFACT_DIR / "v1_release_decision.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise AssertionError(f"Missing Phase 26 artifacts: {missing}")
    audit = load_json(ARTIFACT_DIR / "v1_release_candidate_consolidation_audit.json")
    decision = load_json(ARTIFACT_DIR / "v1_release_decision.json")
    gaps = load_json(ARTIFACT_DIR / "v1_gap_register.json")
    evidence = load_json(ARTIFACT_DIR / "v1_evidence_index.json")
    assert audit["status"] == "V1_RELEASE_CANDIDATE_CONSOLIDATED"
    assert audit["official_certification_claimed"] is False
    assert audit["official_certification_granted"] is False
    assert audit["production_release_authorized"] is False
    assert decision["decision"] == "V1_RELEASE_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW"
    assert decision["human_approval_required_for_release"] is True
    assert gaps["factory_certifies_itself"] is False
    assert len(evidence["evidence_domains"]) >= 8
    print("Phase 26 V1 release-candidate consolidation artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
