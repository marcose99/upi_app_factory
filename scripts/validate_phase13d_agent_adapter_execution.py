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
PHASE_DOCS = ROOT / "docs" / "phase13d"
SRC = ROOT / "src" / "factory_agent_runtime"
LEDGER_ROOT = RUN_ROOT / "agent_runtime_ledgers"
REPORT = RUN_ROOT / "agent_adapter_execution_report.json"
PORTAL = WORKSPACE_ROOT / "audit_portal" / "factory_agent_adapter_portal.html"


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    required = [
        SRC / "adapters.py",
        PHASE_DOCS / "agent_adapter_execution_policy.json",
        PHASE_DOCS / "agent_adapter_execution_architecture.json",
        REPORT,
        PORTAL,
        LEDGER_ROOT / "adapter_capability_ledger.jsonl",
        LEDGER_ROOT / "adapter_execution_ledger.jsonl",
    ]
    for path in required:
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})

    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        default = report["default_adapter_execution"]
        if default["adapter_name"] != "local_deterministic":
            errors.append({"path": str(REPORT.relative_to(ROOT)), "error": "default_adapter_not_local"})
        if default["status"] != "executed":
            errors.append({"path": str(REPORT.relative_to(ROOT)), "error": "default_adapter_not_executed"})
        capability_names = {item["adapter_name"] for item in report["capabilities"]}
        for required_name in ["local_deterministic", "langgraph", "openai_agents"]:
            if required_name not in capability_names:
                errors.append({"path": str(REPORT.relative_to(ROOT)), "error": f"missing_capability:{required_name}"})

    if PORTAL.exists():
        text = PORTAL.read_text(encoding="utf-8")
        for term in [
            "Governed Agent Adapter Portal",
            "Default Adapter Execution",
            "Adapter Capability Cards",
            "LangGraph/OpenAI execution remains human-approval",
        ]:
            if term not in text:
                errors.append({"path": str(PORTAL.relative_to(ROOT)), "error": f"missing:{term}"})

    return {
        "passed": not errors,
        "phase": "Phase 13D",
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
