#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

DOC_PATH = Path("docs/phase14y_z/operator_autonomy_dashboard_v1_readiness_pack.md")
POLICY_PATH = Path("policies/phase14yz_operator_autonomy_v1_readiness_policy.json")
RUNNER_PATH = Path("scripts/run_operator_autonomy_dashboard_v1_readiness_pack.py")
TEST_PATH = Path("tests/test_phase14yz_operator_autonomy_v1_readiness.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14y_z/operator_autonomy_dashboard_v1_readiness_pack_audit.json"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    for path in (DOC_PATH, POLICY_PATH, RUNNER_PATH, TEST_PATH, AUDIT_PATH):
        require(path.exists(), f"missing required artifact: {path}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    doc = DOC_PATH.read_text(encoding="utf-8")
    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    require("Stable endgame runner rule" in doc, "documentation must lock the stable endgame runner rule", errors)
    require("operator autonomy dashboard" in doc.lower(), "documentation must describe operator autonomy dashboard", errors)
    require("v1 autonomous readiness pack" in doc.lower(), "documentation must describe v1 autonomous readiness pack", errors)
    require("certifying authority review" in doc, "documentation must preserve certification boundary", errors)

    require(policy.get("phase") == "14Y-Z", "policy phase must be 14Y-Z", errors)
    require(policy.get("validators_must_be_read_only") is True, "policy must require read-only validators", errors)
    require(policy.get("tests_must_use_temporary_audit_outputs") is True, "policy must require temporary audit outputs", errors)
    require(policy.get("factory_must_not_self_certify") is True, "policy must prohibit self-certification", errors)

    require(audit.get("phase") == "14Y-Z", "audit phase must be 14Y-Z", errors)
    require(audit.get("operator_autonomy_dashboard_enabled") is True, "audit must enable operator autonomy dashboard", errors)
    require(audit.get("v1_autonomous_readiness_pack_enabled") is True, "audit must enable v1 readiness pack", errors)
    require(audit.get("stable_endgame_runner_rule_locked") is True, "audit must lock stable endgame runner rule", errors)
    require(audit.get("factory_does_not_self_certify") is True, "audit must state factory does not self-certify", errors)
    require(audit.get("official_certification_granted_by_factory") is False, "audit must not grant official certification", errors)
    require(audit.get("certification_ready_not_certified_boundary_preserved") is True, "audit must preserve certification boundary", errors)

    dashboard_sections = audit.get("operator_dashboard_sections")
    readiness_sections = audit.get("v1_readiness_pack_sections")
    require(isinstance(dashboard_sections, list) and len(dashboard_sections) >= 8, "audit must include dashboard section evidence", errors)
    require(isinstance(readiness_sections, list) and len(readiness_sections) >= 8, "audit must include v1 readiness pack section evidence", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Phase 14Y-Z operator autonomy dashboard and v1 readiness pack artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
