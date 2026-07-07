from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_phase13y_llm_provider_abstraction_is_secret_safe_and_deterministic() -> None:
    runner = load_module(
        "scripts/run_phase13y_llm_provider_abstraction_secret_safe_openai_readiness.py",
        "phase13y_runner",
    )
    validator = load_module(
        "scripts/validate_phase13y_llm_provider_abstraction_secret_safe_openai_readiness.py",
        "phase13y_validator",
    )
    run_generation = cast(Callable[[Path | None], dict[str, Any]], getattr(runner, "run_generation"))
    validate = cast(Callable[[Path | None], dict[str, Any]], getattr(validator, "validate"))

    result = run_generation(None)
    assert result["passed"] is True
    assert result["llm_runtime_mode"] == "deterministic_local"
    assert result["active_llm_provider"] == "deterministic"
    assert result["openai_provider_mode"] == "configuration_only"
    assert result["openai_api_key_required"] is False
    assert result["openai_api_key_value_serialized"] is False
    assert result["live_llm_call_performed"] is False
    assert result["human_approval_required"] is True
    assert "LLMProviderPort" in result["factory_core_contracts"]
    assert "deterministic" in result["verified_llm_provider_adapters"]
    assert "openai_config_only" in result["verified_llm_provider_adapters"]

    call_evidence = cast(dict[str, Any], result["call_evidence"])
    assert call_evidence["provider"] == "deterministic"
    assert call_evidence["live_call_performed"] is False
    assert call_evidence["prompt_hash"] != ""
    assert call_evidence["response_hash"] != ""

    openai_public = cast(dict[str, Any], result["openai_config_public_metadata"])
    assert openai_public["secret_env_var"] == "OPENAI_API_KEY"
    assert openai_public["secret_value_serialized"] is False

    validation = validate(None)
    assert validation["passed"] is True
    assert validation["secret_value_serialized"] is False
    assert validation["live_llm_call_performed"] is False
