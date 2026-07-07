from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_phase13x_establishes_agent_runtime_abstraction_layer() -> None:
    runner = load_module("scripts/run_phase13x_agent_runtime_abstraction_layer.py", "phase13x_runner")
    run_generation = cast(Callable[[Path | None], dict[str, Any]], getattr(runner, "run_generation"))
    result = run_generation(None)
    assert result["passed"] is True
    assert result["agent_framework_independence_status"] == "adapter_boundary_established"
    assert result["active_framework_adapter"] == "langgraph"
    assert sorted(result["verified_runtime_adapters"]) == ["deterministic", "langgraph"]
    assert "AgentRuntimePort" in result["factory_core_contracts"]
    assert result["openai_api_key_required"] is False

    validator = load_module("scripts/validate_phase13x_agent_runtime_abstraction_layer.py", "phase13x_validator")
    validate = cast(Callable[[Path | None], dict[str, Any]], getattr(validator, "validate"))
    validation = validate(None)
    assert validation["passed"] is True
    assert validation["runtime_independence_passed"] is True
    assert sorted(validation["verified_runtime_adapters"]) == ["deterministic", "langgraph"]
