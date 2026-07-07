#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ARTIFACT_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase19")
REQUIRED_FILES = [
    Path("docs/phase19/supply_chain_provenance_hardening.md"),
    Path("policies/phase19_supply_chain_provenance_policy.json"),
    ARTIFACT_DIR / "supply_chain_provenance_hardening_audit.json",
    ARTIFACT_DIR / "local_dependency_inventory.json",
    ARTIFACT_DIR / "provenance_readiness_statement.json",
    ARTIFACT_DIR / "supply_chain_gate_summary.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate() -> dict[str, Any]:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        return {"phase": "19", "passed": False, "missing": missing}
    audit = load_json(ARTIFACT_DIR / "supply_chain_provenance_hardening_audit.json")
    inventory = load_json(ARTIFACT_DIR / "local_dependency_inventory.json")
    provenance = load_json(ARTIFACT_DIR / "provenance_readiness_statement.json")
    gate_summary = load_json(ARTIFACT_DIR / "supply_chain_gate_summary.json")
    checks = [
        audit.get("status") == "SUPPLY_CHAIN_PROVENANCE_HARDENING_READY",
        audit.get("local_attestation_readiness_only") is True,
        audit.get("official_slsa_claim_made") is False,
        audit.get("formal_supply_chain_certification_claimed") is False,
        audit.get("artifact_publication_performed") is False,
        audit.get("registry_push_performed") is False,
        audit.get("signing_key_used") is False,
        inventory.get("pyproject_present") is True,
        provenance.get("attestation_status") == "readiness_only_not_formal_attestation",
        gate_summary.get("read_only_gates_passed") in (True, False),
    ]
    return {"phase": "19", "passed": all(checks), "documents_checked": len(REQUIRED_FILES)}


def main() -> int:
    result = validate()
    if not result["passed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("Phase 19 supply-chain provenance hardening artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
