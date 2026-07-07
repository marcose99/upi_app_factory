#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase24"
REQUIRED_FILES = [
    Path("docs/phase24/multi_domain_factory_template_readiness.md"),
    Path("policies/phase24_multi_domain_template_policy.json"),
    Path("scripts/run_phase24_multi_domain_factory_template_readiness.py"),
    Path("scripts/validate_phase24_multi_domain_factory_template_readiness.py"),
    Path("tests/test_phase24_multi_domain_factory_template_readiness.py"),
    ARTIFACT_DIR / "multi_domain_template_readiness_audit.json",
    ARTIFACT_DIR / "reusable_domain_template_model.json",
    ARTIFACT_DIR / "domain_adapter_boundary_matrix.json",
    ARTIFACT_DIR / "multi_domain_gap_register.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise AssertionError(f"Missing Phase 24 artifacts: {missing}")
    audit = load_json(ARTIFACT_DIR / "multi_domain_template_readiness_audit.json")
    model = load_json(ARTIFACT_DIR / "reusable_domain_template_model.json")
    adapters = load_json(ARTIFACT_DIR / "domain_adapter_boundary_matrix.json")
    assert audit["status"] == "MULTI_DOMAIN_FACTORY_TEMPLATE_READY"
    assert audit["live_provider_calls"] is False
    assert audit["cross_domain_application_generated"] is False
    assert audit["official_certification_claimed"] is False
    assert model["governance_invariants_preserved"] is True
    assert model["cross_domain_application_generated"] is False
    assert adapters["live_calls"] is False
    print("Phase 24 multi-domain factory template readiness artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
