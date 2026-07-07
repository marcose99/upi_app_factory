#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

PHASE_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase20")
REQUIRED_PATHS = [
    Path("docs/phase20/environment_promotion_governance.md"),
    Path("policies/phase20_environment_promotion_policy.json"),
    Path("scripts/run_phase20_environment_promotion_governance.py"),
    Path("tests/test_phase20_environment_promotion_governance.py"),
    PHASE_DIR / "environment_promotion_governance_audit.json",
    PHASE_DIR / "environment_promotion_matrix.json",
    PHASE_DIR / "rollback_model.json",
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append({"error": "missing_required_path", "path": str(path)})

    if not errors:
        policy = load_json(Path("policies/phase20_environment_promotion_policy.json"))
        audit = load_json(PHASE_DIR / "environment_promotion_governance_audit.json")
        matrix = load_json(PHASE_DIR / "environment_promotion_matrix.json")
        rollback = load_json(PHASE_DIR / "rollback_model.json")
        checks = {
            "policy_blocks_auto_production": policy.get("automatic_production_promotion_allowed") is False,
            "policy_blocks_live_calls": policy.get("live_provider_calls_allowed") is False,
            "audit_ready": audit.get("status") == "ENVIRONMENT_PROMOTION_GOVERNANCE_READY",
            "audit_preserves_certification_boundary": audit.get("official_certification_claimed") is False,
            "matrix_blocks_auto_production": matrix.get("automatic_production_promotion_allowed") is False,
            "rollback_human_gated": rollback.get("rollback_execution_is_human_gated") is True,
        }
        for check, passed in checks.items():
            if not passed:
                errors.append({"error": "failed_check", "check": check})

    return {"phase": "20", "passed": not errors, "errors": errors, "documents_checked": len(REQUIRED_PATHS)}


def main() -> int:
    result = validate()
    if not result["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("Phase 20 environment promotion governance artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
