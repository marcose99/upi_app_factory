#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

PHASE_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase22")
REQUIRED_PATHS = [
    Path("docs/phase22/enterprise_observability_audit_lake_model.md"),
    Path("policies/phase22_enterprise_observability_policy.json"),
    Path("scripts/run_phase22_enterprise_observability_audit_lake_model.py"),
    Path("tests/test_phase22_enterprise_observability_audit_lake_model.py"),
    PHASE_DIR / "enterprise_observability_audit_lake_audit.json",
    PHASE_DIR / "observability_event_taxonomy.json",
    PHASE_DIR / "audit_lake_model.json",
    PHASE_DIR / "telemetry_retention_model.json",
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
        policy = load_json(Path("policies/phase22_enterprise_observability_policy.json"))
        audit = load_json(PHASE_DIR / "enterprise_observability_audit_lake_audit.json")
        taxonomy = load_json(PHASE_DIR / "observability_event_taxonomy.json")
        lake = load_json(PHASE_DIR / "audit_lake_model.json")
        retention = load_json(PHASE_DIR / "telemetry_retention_model.json")
        checks = {
            "policy_blocks_external_telemetry": policy.get("external_telemetry_publish_allowed") is False,
            "policy_blocks_external_lake_mutation": policy.get("external_audit_lake_mutation_allowed") is False,
            "audit_ready": audit.get("status") == "ENTERPRISE_OBSERVABILITY_AUDIT_LAKE_MODEL_READY",
            "audit_blocks_certification_claim": audit.get("official_certification_claimed") is False,
            "taxonomy_blocks_pii": taxonomy.get("pii_allowed") is False,
            "lake_local_only": lake.get("local_evidence_only") is True,
            "retention_human_gated": retention.get("production_retention_activation_is_human_gated") is True,
        }
        for check, passed in checks.items():
            if not passed:
                errors.append({"error": "failed_check", "check": check})
    return {"phase": "22", "passed": not errors, "errors": errors, "documents_checked": len(REQUIRED_PATHS)}


def main() -> int:
    result = validate()
    if not result["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("Phase 22 enterprise observability and audit-lake model artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
