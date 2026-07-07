from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase13z_governed_live_llm_dry_run_gate_blocks_live_call() -> None:
    runner = load_module("scripts/run_phase13z_governed_live_llm_dry_run_gate.py", "phase13z_runner")
    validator = load_module("scripts/validate_phase13z_governed_live_llm_dry_run_gate.py", "phase13z_validator")
    run_generation = cast(Callable[[Path | None], dict[str, Any]], getattr(runner, "run_generation"))
    validate = cast(Callable[[Path | None], dict[str, Any]], getattr(validator, "validate"))

    result = run_generation(None)
    assert result["passed"] is True
    assert result["live_llm_requested"] is True
    assert result["live_llm_call_allowed"] is False
    assert result["live_llm_call_performed"] is False
    assert result["dry_run_blocked_live_call"] is True
    assert result["secret_value_serialized"] is False
    assert result["openai_api_key_value_serialized"] is False
    assert result["human_approval_required_before_live_llm"] is True
    assert result["llm_call_dry_run_evidence"]["live_call_performed"] is False

    validation = validate(None)
    assert validation["passed"] is True
    assert validation["live_llm_call_performed"] is False
    assert validation["dry_run_blocked_live_call"] is True
