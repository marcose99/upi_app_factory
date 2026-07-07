#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase25"
REQUIRED_FILES = [
    Path("docs/phase25/enterprise_operating_model_pack.md"),
    Path("policies/phase25_enterprise_operating_model_policy.json"),
    Path("scripts/run_phase25_enterprise_operating_model_pack.py"),
    Path("scripts/validate_phase25_enterprise_operating_model_pack.py"),
    Path("tests/test_phase25_enterprise_operating_model_pack.py"),
    ARTIFACT_DIR / "enterprise_operating_model_audit.json",
    ARTIFACT_DIR / "operating_model_raci.json",
    ARTIFACT_DIR / "runbook_index.json",
    ARTIFACT_DIR / "change_incident_release_governance.json",
    ARTIFACT_DIR / "support_handoff_model.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise AssertionError(f"Missing Phase 25 artifacts: {missing}")
    audit = load_json(ARTIFACT_DIR / "enterprise_operating_model_audit.json")
    raci = load_json(ARTIFACT_DIR / "operating_model_raci.json")
    governance = load_json(ARTIFACT_DIR / "change_incident_release_governance.json")
    assert audit["status"] == "ENTERPRISE_OPERATING_MODEL_PACK_READY"
    assert audit["auto_production_deployment"] is False
    assert audit["destructive_actions_automated"] is False
    assert audit["official_certification_claimed"] is False
    assert raci["human_approval_required_for_release"] is True
    assert governance["release_governance"] == "human_approved_merge_tag_release"
    print("Phase 25 enterprise operating model pack artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
