from __future__ import annotations
from typing import Any

import importlib.util
import json
from pathlib import Path

from factory_agent_runtime import GovernedAgentRuntime, RuntimeMode


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase13c_agent_runtime_foundation.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_phase13c_agent_runtime_foundation",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runtime_dry_run_completes_all_registered_agents(tmp_path: Path) -> None:
    runtime = GovernedAgentRuntime(
        app_id="upi_dispute_resolution",
        run_id="test_run",
        workspace_root=tmp_path,
        runtime_mode=RuntimeMode.DRY_RUN,
    )
    state = runtime.run_dry_run()
    assert state.metrics["agents_registered"] == 8
    assert state.metrics["tools_registered"] == 7
    assert state.metrics["agent_steps_completed"] == 8
    assert len(state.completed_agents) == 8


def test_phase13c_agent_runtime_validator_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
