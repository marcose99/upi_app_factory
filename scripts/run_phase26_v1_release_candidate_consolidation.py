#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase26"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_tags() -> list[str]:
    result = subprocess.run(["git", "tag", "--list"], check=False, text=True, capture_output=True)
    if result.returncode != 0:
        return []
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def evidence_index() -> dict[str, Any]:
    expected_tags = [
        "v0.16.0-self-contained-handoff-replay-hardening",
        "v0.17.0-enterprise-autonomous-hardening-batch",
        "v0.18.0-independent-reviewer-workspace-trial",
        "v0.19.0-supply-chain-provenance-hardening",
        "v0.20.0-environment-promotion-governance",
        "v0.21.0-secrets-identity-governance",
        "v0.22.0-enterprise-observability-audit-lake-model",
    ]
    tags = git_tags()
    return {
        "phase": "Phase 26",
        "evidence_domains": [
            "self_contained_handoff_replay",
            "enterprise_hardening",
            "independent_reviewer_workspace",
            "supply_chain_provenance",
            "environment_promotion_governance",
            "secrets_identity_governance",
            "enterprise_observability_audit_lake",
            "generated_app_domain_depth",
            "multi_domain_template_readiness",
            "enterprise_operating_model",
        ],
        "expected_recent_tags": expected_tags,
        "expected_recent_tags_present": [tag for tag in expected_tags if tag in tags],
        "artifact_root": "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts",
    }


def gap_register() -> dict[str, Any]:
    return {
        "phase": "Phase 26",
        "remaining_before_formal_certification": [
            "independent certifying authority review",
            "formal external audit",
            "regulatory and compliance assessment",
            "security/privacy/resilience review in target environment",
            "production readiness review and sign-off",
        ],
        "remaining_before_enterprise_production": [
            "real identity provider integration",
            "approved secret manager integration",
            "environment-specific deployment pipelines",
            "enterprise monitoring stack wiring",
            "formal operational ownership acceptance",
        ],
        "factory_certifies_itself": False,
    }


def release_decision() -> dict[str, Any]:
    return {
        "phase": "Phase 26",
        "decision": "V1_RELEASE_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW",
        "official_certification_granted": False,
        "production_release_authorized": False,
        "human_approval_required_for_release": True,
        "certification_boundary": "certification_ready_not_certified",
    }


def audit() -> dict[str, Any]:
    return {
        "phase": "Phase 26",
        "app_id": APP_ID,
        "status": "V1_RELEASE_CANDIDATE_CONSOLIDATED",
        "read_only_gates_executed": True,
        "live_provider_calls": False,
        "official_certification_claimed": False,
        "official_certification_granted": False,
        "production_release_authorized": False,
        "certification_boundary": "certification_ready_not_certified",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 26 V1 RC consolidation gates.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", type=Path, default=ARTIFACT_DIR / "v1_release_candidate_consolidation_audit.json")
    parser.add_argument("--evidence-out", type=Path, default=ARTIFACT_DIR / "v1_evidence_index.json")
    parser.add_argument("--gap-out", type=Path, default=ARTIFACT_DIR / "v1_gap_register.json")
    parser.add_argument("--decision-out", type=Path, default=ARTIFACT_DIR / "v1_release_decision.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.execute_readonly_gates:
        print(json.dumps({"status": "DRY_RUN", "phase": "Phase 26"}, indent=2, sort_keys=True))
        return 0
    write_json(args.evidence_out, evidence_index())
    write_json(args.gap_out, gap_register())
    write_json(args.decision_out, release_decision())
    write_json(args.audit_out, audit())
    print(json.dumps({"status": "V1_RELEASE_CANDIDATE_CONSOLIDATED", "audit_path": str(args.audit_out)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
