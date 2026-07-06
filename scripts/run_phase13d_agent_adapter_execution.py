#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from factory_agent_runtime import GovernedAdapterExecutor


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
RUN_ROOT = WORKSPACE_ROOT / "generation_runs" / RUN_ID


def main() -> int:
    executor = GovernedAdapterExecutor(
        app_id=APP_ID,
        run_id=RUN_ID,
        workspace_root=WORKSPACE_ROOT,
    )
    capabilities = executor.capability_report()
    result = executor.execute_default_governed_adapter()
    report = {
        "phase": "Phase 13D",
        "run_id": RUN_ID,
        "default_adapter_execution": {
            "adapter_name": result.adapter_name.value,
            "status": result.status.value,
            "message": result.message,
            "metrics": result.metrics,
        },
        "capabilities": [
            {
                "adapter_name": item.adapter_name.value,
                "status": item.status.value,
                "reason": item.reason,
                "requires_network": item.requires_network,
                "requires_secret": item.requires_secret,
                "requires_human_approval": item.requires_human_approval,
            }
            for item in capabilities
        ],
        "truth_boundary": (
            "Only the local deterministic adapter is executed by default. "
            "LangGraph/OpenAI execution remains policy-gated."
        ),
    }
    output = RUN_ROOT / "agent_adapter_execution_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
