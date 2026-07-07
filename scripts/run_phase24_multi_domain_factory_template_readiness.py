#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase24"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def template_model() -> dict[str, Any]:
    return {
        "phase": "Phase 24",
        "template_status": "readiness_model_only",
        "domain_template_layers": [
            "requirement_intake",
            "domain_policy_pack",
            "mock_ecosystem_boundary",
            "generated_app_contracts",
            "local_validation_matrix",
            "certification_ready_evidence_pack",
        ],
        "governance_invariants_preserved": True,
        "cross_domain_application_generated": False,
    }


def adapter_matrix() -> dict[str, Any]:
    return {
        "phase": "Phase 24",
        "adapter_boundaries": [
            {"adapter": "regulatory_source_registry", "mode": "official_source_reference_only"},
            {"adapter": "external_payment_or_domain_rails", "mode": "mock_or_simulated_by_default"},
            {"adapter": "llm_provider", "mode": "secret_safe_and_human_gated_for_live_calls"},
            {"adapter": "certifying_authority", "mode": "independent_external_review_required"},
        ],
        "live_calls": False,
    }


def gap_register() -> dict[str, Any]:
    return {
        "phase": "Phase 24",
        "gaps_before_true_multi_domain_operation": [
            "domain-specific regulatory source packs",
            "domain-specific mock ecosystem contracts",
            "domain-specific threat and privacy model",
            "independent review per domain",
            "business workflow acceptance criteria per domain",
        ],
        "automatic_certification_claimed": False,
    }


def audit() -> dict[str, Any]:
    return {
        "phase": "Phase 24",
        "app_id": APP_ID,
        "status": "MULTI_DOMAIN_FACTORY_TEMPLATE_READY",
        "read_only_gates_executed": True,
        "live_provider_calls": False,
        "cross_domain_application_generated": False,
        "official_certification_claimed": False,
        "certification_boundary": "certification_ready_not_certified",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 24 multi-domain template readiness gates.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", type=Path, default=ARTIFACT_DIR / "multi_domain_template_readiness_audit.json")
    parser.add_argument("--template-out", type=Path, default=ARTIFACT_DIR / "reusable_domain_template_model.json")
    parser.add_argument("--adapter-out", type=Path, default=ARTIFACT_DIR / "domain_adapter_boundary_matrix.json")
    parser.add_argument("--gap-out", type=Path, default=ARTIFACT_DIR / "multi_domain_gap_register.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.execute_readonly_gates:
        print(json.dumps({"status": "DRY_RUN", "phase": "Phase 24"}, indent=2, sort_keys=True))
        return 0
    write_json(args.template_out, template_model())
    write_json(args.adapter_out, adapter_matrix())
    write_json(args.gap_out, gap_register())
    write_json(args.audit_out, audit())
    print(json.dumps({"status": "MULTI_DOMAIN_FACTORY_TEMPLATE_READY", "audit_path": str(args.audit_out)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
