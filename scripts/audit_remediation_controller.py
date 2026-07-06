#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "phase12b" / "audit_remediation_policy.json"
QUALITY_OBJECTIVES = ROOT / "docs" / "phase12b" / "quality_objectives.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_finding(finding: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    category = str(finding.get("category", "unknown"))
    severity = str(finding.get("severity", "unknown")).lower()

    allowed_categories = set(policy["allowed_auto_apply_categories"])
    protected_categories = {
        "security_policy",
        "tool_authorization",
        "regulatory_claim",
        "live_integration",
        "customer_data",
        "quality_waiver",
    }

    is_low_risk_allowed = category in allowed_categories and severity not in {"high", "critical"}
    is_protected = severity in {"high", "critical"} or category in protected_categories
    auto_apply_candidate = is_low_risk_allowed and not is_protected

    return {
        "finding_id": finding.get("finding_id", "UNKNOWN"),
        "category": category,
        "severity": severity,
        "auto_apply_candidate": auto_apply_candidate,
        "human_approval_required": not auto_apply_candidate,
        "reason": (
            "low-risk allowed category"
            if auto_apply_candidate
            else "human approval required by policy"
        ),
    }


def plan_remediation(audit_report: dict[str, Any]) -> dict[str, Any]:
    policy = load_json(POLICY)
    objectives = load_json(QUALITY_OBJECTIVES)
    findings = audit_report.get("findings", [])

    if not isinstance(findings, list):
        raise ValueError("audit_report.findings must be a list")

    planned = [classify_finding(finding, policy) for finding in findings]
    return {
        "mode": "plan_only",
        "policy": str(POLICY.relative_to(ROOT)),
        "quality_objectives": str(QUALITY_OBJECTIVES.relative_to(ROOT)),
        "minimum_scores": objectives["minimum_scores"],
        "hard_gates": objectives["hard_gates"],
        "max_remediation_cycles": policy["max_remediation_cycles"],
        "max_attempts_per_finding": policy["max_attempts_per_finding"],
        "stop_conditions": policy["stop_conditions"],
        "planned_remediations": planned,
        "note": (
            "This controller is intentionally plan-only in Phase 12B. "
            "Auto-apply is enabled only in a later phase after policy and "
            "human approval gates are validated."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan audit-driven remediation from a structured audit report."
    )
    parser.add_argument("--audit-report", required=True, help="Path to structured audit report JSON.")
    parser.add_argument("--out", required=False, help="Optional output JSON path.")
    args = parser.parse_args()

    report_path = Path(args.audit_report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path

    audit_report = load_json(report_path)
    plan = plan_remediation(audit_report)

    output = json.dumps(plan, indent=2, sort_keys=True)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\\n", encoding="utf-8")
        print(out_path)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
