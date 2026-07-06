#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from factory_agent_runtime import GovernedAgentRuntime, RuntimeMode


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID


def main() -> int:
    runtime = GovernedAgentRuntime(
        app_id=APP_ID,
        run_id=RUN_ID,
        workspace_root=WORKSPACE_ROOT,
        runtime_mode=RuntimeMode.DRY_RUN,
    )
    state = runtime.run_dry_run()
    snapshot = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "agent_runtime_state_snapshot.json"
    snapshot.write_text(json.dumps(state.to_jsonable(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(state.to_jsonable(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
