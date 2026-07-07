#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase23"
REQUIRED_FILES = [
    Path("docs/phase23/generated_app_domain_depth_hardening.md"),
    Path("policies/phase23_generated_app_domain_depth_policy.json"),
    Path("scripts/run_phase23_generated_app_domain_depth_hardening.py"),
    Path("scripts/validate_phase23_generated_app_domain_depth_hardening.py"),
    Path("tests/test_phase23_generated_app_domain_depth_hardening.py"),
    ARTIFACT_DIR / "generated_app_domain_depth_audit.json",
    ARTIFACT_DIR / "workflow_depth_matrix.json",
    ARTIFACT_DIR / "negative_resilience_scenario_catalog.json",
    ARTIFACT_DIR / "generated_app_quality_gap_register.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise AssertionError(f"Missing Phase 23 artifacts: {missing}")
    audit = load_json(ARTIFACT_DIR / "generated_app_domain_depth_audit.json")
    matrix = load_json(ARTIFACT_DIR / "workflow_depth_matrix.json")
    gaps = load_json(ARTIFACT_DIR / "generated_app_quality_gap_register.json")
    assert audit["status"] == "GENERATED_APP_DOMAIN_DEPTH_HARDENING_READY"
    assert audit["live_provider_calls"] is False
    assert audit["production_data_accessed"] is False
    assert audit["generated_app_business_logic_mutated"] is False
    assert audit["official_certification_claimed"] is False
    assert audit["certification_boundary"] == "certification_ready_not_certified"
    assert matrix["external_integrations"] == "simulated_only"
    assert len(matrix["workflows"]) >= 3
    assert gaps["not_certified_by_factory"] is True
    print("Phase 23 generated app domain-depth hardening artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
