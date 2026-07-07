from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_phase13aa_replays_llm_evidence_without_secret_serialization() -> None:
    runner = load_module(
        "scripts/run_phase13aa_llm_evidence_replay_redaction_validator.py",
        "phase13aa_runner",
    )
    validator = load_module(
        "scripts/validate_phase13aa_llm_evidence_replay_redaction_validator.py",
        "phase13aa_validator",
    )
    run_generation = cast(Callable[[Path | None], dict[str, Any]], getattr(runner, "run_generation"))
    validate = cast(Callable[[Path | None], dict[str, Any]], getattr(validator, "validate"))

    result = run_generation(None)
    assert result["passed"] is True
    assert result["live_llm_call_performed"] is False
    assert result["secret_value_serialized"] is False
    assert result["metadata_replay_passed"] is True
    assert result["policy_id"] == "POL-13AA-LLM-EVIDENCE-REPLAY-REDACTION"

    validation = validate(None)
    assert validation["passed"] is True
    assert validation["secret_value_serialized"] is False
    assert validation["metadata_replay_passed"] is True
