from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase11c_llm_call_metrics_prompt_policy.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("phase11c_llm_metrics_validator", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase11c_llm_call_metrics_prompt_policy_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
    assert result["prompt_files_checked"] >= 50


def test_phase11c_llm_prompt_scope_excludes_governance_reference_docs() -> None:
    validator = load_validator()
    prompt_paths = {str(path.relative_to(ROOT)) for path in validator.prompt_files()}
    assert "factory_governance/01_PROJECT_CHARTER.md" not in prompt_paths
    assert "factory_governance/templates/architecture_decision_record_template.v1.md" not in prompt_paths
    assert "docs/phase8_governed_multi_agent_role_simulation.md" not in prompt_paths


def test_phase11c_llm_call_metrics_required_terms_are_complete() -> None:
    validator = load_validator()
    terms = validator.required_terms()
    for expected in (
        "call_id",
        "build_id",
        "prompt_version_or_hash",
        "cached_input_tokens",
        "reasoning_tokens",
        "llm_call_metrics_ledger.jsonl",
        "llm_expense_summary.json",
        "no additional LLM calls are allowed",
        "real, locally runnable software",
        "mock/simulated",
    ):
        assert expected in terms
