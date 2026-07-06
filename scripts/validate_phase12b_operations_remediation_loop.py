#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DOCS = ROOT / "docs" / "phase12b"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase12b"
CONTROLLER = ROOT / "scripts" / "audit_remediation_controller.py"

REQUIRED_FILES = [
    "factory_operations_runbook.md",
    "generated_application_operations_runbook.md",
    "audit_to_remediation_runbook.md",
    "incident_response_runbook.md",
    "release_and_rollback_runbook.md",
    "human_approval_runbook.md",
    "final_report_and_portal_runbook.md",
    "quality_objectives.json",
    "audit_remediation_policy.json",
    "audit_remediation_attempt_ledger_schema.json",
    "audit_remediation_loop_state_machine.json",
    "final_audit_report_fact_contract.json",
    "operations_runbook_index.json",
    "phase12b_readiness_report.md",
]

REQUIRED_TERMS = {
    "factory_operations_runbook.md": ["operate the Agentic AI factory", "Stop immediately", "real customer data"],
    "generated_application_operations_runbook.md": ["locally runnable", "mock/simulated", "Required operational evidence"],
    "audit_to_remediation_runbook.md": ["Normalize findings", "Compare before/after scores", "QUALITY_OBJECTIVES_MET"],
    "incident_response_runbook.md": ["real customer data detected", "live integration attempt detected", "preserve logs and evidence"],
    "release_and_rollback_runbook.md": ["all quality objectives met", "final audit report generated", "last known good tag"],
    "human_approval_runbook.md": ["Human approval is required", "tool authorization expansion", "quality objective waiver"],
    "final_report_and_portal_runbook.md": ["remediation cycles with before/after scores", "Every major statement must map to evidence paths"],
    "quality_objectives.json": ["minimum_scores", "factory_governance", "human_validator_portal", "quality_objectives_met_rule"],
    "audit_remediation_policy.json": ["max_remediation_cycles", "allowed_auto_apply_categories", "human_approval_required_for", "stop_conditions"],
    "audit_remediation_attempt_ledger_schema.json": ["remediation_attempt_id", "before_scores", "after_scores", "rollback_plan"],
    "audit_remediation_loop_state_machine.json": ["INGEST_AUDIT_REPORT", "PLAN_REMEDIATION", "UPDATE_REPORT_AND_PORTAL"],
    "final_audit_report_fact_contract.json": ["remediation_cycles", "before_after_scores", "human_validator_portal_link"],
    "operations_runbook_index.json": ["factory_operations_runbook.md", "audit_to_remediation_runbook.md"],
    "phase12b_readiness_report.md": ["OPERATIONS AND REMEDIATION CONTROL PLANE READY", "does not yet perform automatic remediation"],
}


def _check_root(root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for name in REQUIRED_FILES:
        path = root / name
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})
            continue
        text = path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS.get(name, []):
            if term not in text:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"missing_term:{term}"})
    return errors


def validate() -> dict[str, Any]:
    errors = _check_root(DOCS) + _check_root(WORKSPACE)

    if not CONTROLLER.exists():
        errors.append({"path": str(CONTROLLER.relative_to(ROOT)), "error": "missing_remediation_controller"})
    else:
        text = CONTROLLER.read_text(encoding="utf-8")
        for term in ["plan_only", "human_approval_required", "allowed_auto_apply_categories"]:
            if term not in text:
                errors.append({"path": str(CONTROLLER.relative_to(ROOT)), "error": f"missing_controller_term:{term}"})

    policy_path = DOCS / "audit_remediation_policy.json"
    if policy_path.exists():
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        if policy.get("max_remediation_cycles") != 3:
            errors.append({"path": str(policy_path.relative_to(ROOT)), "error": "unexpected_max_remediation_cycles"})
        if "git push" not in policy.get("human_approval_required_for", []):
            errors.append({"path": str(policy_path.relative_to(ROOT)), "error": "git_push_approval_not_required"})
        if "QUALITY_OBJECTIVES_MET" not in policy.get("stop_conditions", []):
            errors.append({"path": str(policy_path.relative_to(ROOT)), "error": "missing_quality_objectives_stop_condition"})

    return {
        "passed": not errors,
        "phase": "Phase 12B",
        "app_id": APP_ID,
        "docs_files_checked": len(REQUIRED_FILES),
        "workspace_files_checked": len(REQUIRED_FILES),
        "controller_checked": CONTROLLER.exists(),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
