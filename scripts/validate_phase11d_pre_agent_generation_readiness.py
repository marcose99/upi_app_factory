#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DOCS = ROOT / "docs" / "phase11d"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase11d"

REQUIRED_FILES = [
    "pre_agent_generation_readiness_review.md",
    "prompt_policy_manifest.json",
    "agent_orchestration_contract.json",
    "tool_authorization_policy.json",
    "memory_retrieval_context_policy.json",
    "architecture_hld_lld_quality_gate.md",
    "test_evaluation_quality_gate.md",
    "risk_policy_control_matrix.json",
    "observability_audit_logging_contract.json",
    "upi_domain_policy_execution_gap_register.md",
    "pre_generation_go_no_go_report.json",
]

REQUIRED_TERMS = {
    "prompt_policy_manifest.json": [
        "prompt_inheritance_model",
        "conflict_resolution_order",
        "upi_domain_safety_regulatory_guardrails",
    ],
    "agent_orchestration_contract.json": [
        "orchestration_order",
        "handoff_contract",
        "retry_budget",
        "human_approval_required",
    ],
    "tool_authorization_policy.json": [
        "default",
        "deny",
        "network_access",
        "approval_required_for",
        "live NPCI calls",
        "real customer data access",
    ],
    "memory_retrieval_context_policy.json": [
        "memory_is_run_scoped",
        "rag_sources_allowed",
        "citation_required",
        "context_budget_required",
    ],
    "architecture_hld_lld_quality_gate.md": [
        "architecture_decision_records",
        "hld.md",
        "lld.md",
        "workflow_state_machine",
        "observability_design",
    ],
    "test_evaluation_quality_gate.md": [
        "unit tests",
        "integration tests",
        "domain scenario tests",
        "limited local load tests",
        "limited local stress tests",
        "security tests",
    ],
    "risk_policy_control_matrix.json": [
        "regulatory_misclaim",
        "mock_boundary_violation",
        "tool_overreach",
        "rag_poisoning",
        "risk_acceptance_requires_human_review",
    ],
    "observability_audit_logging_contract.json": [
        "llm_call_metrics_ledger.jsonl",
        "tool_execution_ledger.jsonl",
        "agent_handoff_ledger.jsonl",
        "guardrail_tripwire",
        "append_only",
    ],
    "upi_domain_policy_execution_gap_register.md": [
        "failed_transaction_tat_rules.json",
        "complaint_lifecycle_state_machine.json",
        "unauthorized_transaction_handling_rules.json",
        "odr_escalation_policy.json",
    ],
    "pre_generation_go_no_go_report.json": [
        "GO",
        "blocked_generation_conditions",
        "first governed agent application generation run",
    ],
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_root(root: Path) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for name in REQUIRED_FILES:
        path = root / name
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})
            continue

        text = _read(path)
        for term in REQUIRED_TERMS.get(name, []):
            if term not in text:
                errors.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "error": f"missing_term:{term}",
                    }
                )

    return errors


def validate() -> dict[str, Any]:
    errors = _check_root(DOCS) + _check_root(WORKSPACE)

    go_no_go = DOCS / "pre_generation_go_no_go_report.json"
    if go_no_go.exists():
        data = json.loads(go_no_go.read_text(encoding="utf-8"))
        if data.get("decision") != "GO":
            errors.append(
                {
                    "path": str(go_no_go.relative_to(ROOT)),
                    "error": "go_no_go_decision_is_not_GO",
                }
            )

    return {
        "passed": not errors,
        "phase": "Phase 11D",
        "app_id": APP_ID,
        "docs_artifacts_checked": len(REQUIRED_FILES),
        "workspace_artifacts_checked": len(REQUIRED_FILES),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
