from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str) -> ModuleType:
    module_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Runtime type-hint consumers such as LangGraph need the dynamically
    # loaded module registered so ForwardRef names resolve correctly.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_phase13w_generates_governed_multi_capability_application() -> None:
    runner = load_module(
        "scripts/run_phase13w_governed_multi_capability_application_assembly.py",
        "phase13w_runner",
    )
    run_generation = cast(Callable[[Path | None], dict[str, Any]], getattr(runner, "run_generation"))
    result = run_generation(None)

    assert result["passed"] is True
    assert result["graph_type"] == "StateGraph"
    assert result["capability_count"] >= 2
    assert set(result["assembled_capabilities"]) == {"evidence_validation", "sla_triage"}
    assert result["external_ecosystem_boundary"] == "mock_only"
    assert result["human_approval_required"] is True
    assert result["openai_api_key_required"] is False

    validator = load_module(
        "scripts/validate_phase13w_governed_multi_capability_application_assembly.py",
        "phase13w_validator",
    )
    validate = cast(Callable[[], dict[str, Any]], getattr(validator, "validate"))
    validation = validate()

    assert validation["passed"] is True
    assert validation["policy_decision_count"] >= 1
    assert validation["capability_count"] >= 2
