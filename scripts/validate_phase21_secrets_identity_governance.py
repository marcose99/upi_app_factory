#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

PHASE_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase21")
REQUIRED_PATHS = [
    Path("docs/phase21/secrets_identity_governance.md"),
    Path("policies/phase21_secrets_identity_policy.json"),
    Path("scripts/run_phase21_secrets_identity_governance.py"),
    Path("tests/test_phase21_secrets_identity_governance.py"),
    PHASE_DIR / "secrets_identity_governance_audit.json",
    PHASE_DIR / "identity_boundary_matrix.json",
    PHASE_DIR / "secret_handling_evidence.json",
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
        policy = load_json(Path("policies/phase21_secrets_identity_policy.json"))
        audit = load_json(PHASE_DIR / "secrets_identity_governance_audit.json")
        identity = load_json(PHASE_DIR / "identity_boundary_matrix.json")
        secrets = load_json(PHASE_DIR / "secret_handling_evidence.json")
        checks = {
            "policy_blocks_real_secret_storage": policy.get("real_secret_storage_allowed") is False,
            "policy_blocks_idp_calls": policy.get("live_identity_provider_calls_allowed") is False,
            "audit_ready": audit.get("status") == "SECRETS_IDENTITY_GOVERNANCE_READY",
            "audit_blocks_certification_claim": audit.get("official_certification_claimed") is False,
            "identity_no_mutation": identity.get("identity_provider_mutation_performed") is False,
            "secrets_not_materialized": secrets.get("secret_values_materialized") is False,
        }
        for check, passed in checks.items():
            if not passed:
                errors.append({"error": "failed_check", "check": check})
    return {"phase": "21", "passed": not errors, "errors": errors, "documents_checked": len(REQUIRED_PATHS)}


def main() -> int:
    result = validate()
    if not result["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("Phase 21 secrets and identity governance artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
