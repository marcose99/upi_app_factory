#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ARTIFACT_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase18")
REQUIRED_FILES = [
    Path("docs/phase18/independent_reviewer_workspace_trial.md"),
    Path("policies/phase18_independent_reviewer_workspace_policy.json"),
    ARTIFACT_DIR / "independent_reviewer_workspace_trial_audit.json",
    ARTIFACT_DIR / "independent_reviewer_workspace_pack.json",
    ARTIFACT_DIR / "independent_reviewer_checklist.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate() -> dict[str, Any]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return {"phase": "18", "passed": False, "missing": missing}
    audit = load_json(ARTIFACT_DIR / "independent_reviewer_workspace_trial_audit.json")
    pack = load_json(ARTIFACT_DIR / "independent_reviewer_workspace_pack.json")
    checklist = load_json(ARTIFACT_DIR / "independent_reviewer_checklist.json")
    checks = [
        audit.get("status") == "INDEPENDENT_REVIEWER_WORKSPACE_TRIAL_READY",
        audit.get("factory_does_not_self_certify") is True,
        audit.get("official_certification_claimed") is False,
        audit.get("official_certification_granted_by_factory") is False,
        pack.get("requires_external_provider") is False,
        pack.get("requires_hidden_local_workspace_state") is False,
        "do_not_treat_factory_output_as_certification" in checklist.get("items", []),
    ]
    return {"phase": "18", "passed": all(checks), "documents_checked": len(REQUIRED_FILES)}


def main() -> int:
    result = validate()
    if not result["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("Phase 18 independent reviewer workspace trial artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
