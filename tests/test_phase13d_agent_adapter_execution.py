from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from factory_agent_runtime import AdapterCapabilityDetector, GovernedAdapterExecutor


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase13d_agent_adapter_execution.py"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_phase13d_agent_adapter_execution",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_adapter_capability_detector_reports_all_adapter_types() -> None:
    capabilities = AdapterCapabilityDetector().detect()
    names = {item.adapter_name.value for item in capabilities}
    assert names == {"local_deterministic", "langgraph", "openai_agents"}


def test_governed_adapter_executor_runs_local_deterministic_adapter(tmp_path: Path) -> None:
    executor = GovernedAdapterExecutor(
        app_id="upi_dispute_resolution",
        run_id="test_run",
        workspace_root=tmp_path,
    )
    result = executor.execute_default_governed_adapter()
    assert result.adapter_name.value == "local_deterministic"
    assert result.status.value == "executed"
    assert result.metrics["completed_agents"] == 8


def test_phase13d_agent_adapter_validator_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
