#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ARTIFACT_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase17")
REQUIRED_FILES = [
    Path("docs/phase17/enterprise_autonomous_hardening.md"),
    Path("policies/phase17_enterprise_autonomous_hardening_policy.json"),
    ARTIFACT_DIR / "enterprise_autonomous_hardening_audit.json",
    ARTIFACT_DIR / "release_dossier_index.json",
    ARTIFACT_DIR / "independent_reviewer_workspace_trial.json",
    ARTIFACT_DIR / "generated_app_depth_backlog.json",
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate() -> dict[str, Any]:
    errors: list[str] = []
    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing:{path}")
    if errors:
        return {"phase": "17", "passed": False, "errors": errors}

    audit = load_json(ARTIFACT_DIR / "enterprise_autonomous_hardening_audit.json")
    dossier = load_json(ARTIFACT_DIR / "release_dossier_index.json")
    reviewer = load_json(ARTIFACT_DIR / "independent_reviewer_workspace_trial.json")
    backlog = load_json(ARTIFACT_DIR / "generated_app_depth_backlog.json")

    checks = [
        audit.get("status") == "ENTERPRISE_AUTONOMOUS_HARDENING_READY",
        audit.get("factory_does_not_self_certify") is True,
        audit.get("official_certification_claimed") is False,
        audit.get("official_certification_granted_by_factory") is False,
        audit.get("live_provider_calls_performed") is False,
        audit.get("external_system_mutation_performed") is False,
        dossier.get("contains_official_certification_claim") is False,
        reviewer.get("fresh_clone_replay_required") is True,
        reviewer.get("hidden_local_workspace_state_required") is False,
        bool(backlog.get("items")),
    ]
    require(all(checks), "Phase 17 enterprise hardening evidence failed governance checks")
    return {"phase": "17", "passed": True, "documents_checked": len(REQUIRED_FILES)}


def main() -> int:
    result = validate()
    if not result["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("Phase 17 enterprise autonomous hardening artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
