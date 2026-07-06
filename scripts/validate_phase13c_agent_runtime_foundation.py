#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DOCS = ROOT / "docs" / "phase13c"
SRC = ROOT / "src" / "factory_agent_runtime"
LEDGER_ROOT = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "agent_runtime_ledgers"
STATE = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "agent_runtime_state_snapshot.json"
PORTAL = WORKSPACE_ROOT / "audit_portal" / "factory_agent_runtime_portal.html"


def validate() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    required = [
        SRC / "__init__.py",
        SRC / "contracts.py",
        SRC / "registry.py",
        SRC / "ledger.py",
        SRC / "orchestrator.py",
        PHASE_DOCS / "agent_registry.json",
        PHASE_DOCS / "tool_registry.json",
        PHASE_DOCS / "agent_runtime_architecture.json",
        PHASE_DOCS / "agent_runtime_state_schema.json",
        PHASE_DOCS / "live_portal_telemetry_contract.json",
        STATE,
        LEDGER_ROOT / "runtime_event_ledger.jsonl",
        LEDGER_ROOT / "handoff_ledger.jsonl",
        LEDGER_ROOT / "tool_execution_ledger.jsonl",
        PORTAL,
    ]
    for path in required:
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})

    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if state.get("runtime_mode") != "dry_run":
            errors.append({"path": str(STATE.relative_to(ROOT)), "error": "runtime_mode_not_dry_run"})
        if len(state.get("completed_agents", [])) < 7:
            errors.append({"path": str(STATE.relative_to(ROOT)), "error": "too_few_completed_agents"})

    if PORTAL.exists():
        text = PORTAL.read_text(encoding="utf-8")
        for term in [
            "Governed Agent Runtime Portal",
            "Agent Sequence Graph",
            "Runtime Ledger Metrics",
            "dry-run execution",
            "LangGraph/OpenAI-agent LLM execution is planned next",
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
