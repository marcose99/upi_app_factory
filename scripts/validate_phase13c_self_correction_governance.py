#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
RUN_ROOT = WORKSPACE_ROOT / "generation_runs" / RUN_ID
PHASE_DOCS = ROOT / "docs" / "phase13c"
SRC = ROOT / "src" / "factory_agent_runtime"
LEDGER_ROOT = RUN_ROOT / "agent_runtime_ledgers"
REPORT = RUN_ROOT / "self_correction" / "self_correction_decisions.json"
PORTAL = WORKSPACE_ROOT / "audit_portal" / "factory_self_correction_portal.html"


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    required = [
        SRC / "self_correction.py",
        PHASE_DOCS / "agent_self_correction_policy.json",
        PHASE_DOCS / "agent_self_correction_contract.json",
        REPORT,
        LEDGER_ROOT / "self_correction_decision_ledger.jsonl",
        LEDGER_ROOT / "self_correction_attempt_ledger.jsonl",
        PORTAL,
    ]
    for path in required:
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})

    if REPORT.exists():
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        summary = data["summary"]
        if summary["untriaged"] != 0:
            errors.append({"path": str(REPORT.relative_to(ROOT)), "error": "untriaged_findings"})
        if summary["total_decisions"] != len(data["decisions"]):
            errors.append({"path": str(REPORT.relative_to(ROOT)), "error": "decision_count_mismatch"})
        actions = {item["action"] for item in data["decisions"]}
        for action in ["auto_remediate", "human_approval_required", "blocked"]:
            if action not in actions:
                errors.append({"path": str(REPORT.relative_to(ROOT)), "error": f"missing_action:{action}"})

    if PORTAL.exists():
        text = PORTAL.read_text(encoding="utf-8")
        for term in [
            "Governed Self-Correction Portal",
            "Every warning/error is triaged",
            "Auto remediate",
            "Human approval required",
            "Blocked",
            "Untriaged",
        ]:
            if term not in text:
                errors.append({"path": str(PORTAL.relative_to(ROOT)), "error": f"missing:{term}"})

    return {
        "passed": not errors,
        "phase": "Phase 13C",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
