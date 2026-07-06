from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase11c_agentic_prompt_best_practices.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("phase11c_agentic_prompt_validator", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase11c_agentic_prompt_best_practices_pass() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
    assert result["prompt_files_checked"] >= 50


def test_phase11c_generated_application_quality_terms_are_enforced() -> None:
    validator = load_validator()
    checks = validator.BEST_PRACTICE_TERMS
    for expected_check in (
        "generated_application_type_best_practices",
        "code_quality_reporting",
        "unit_testing",
        "integration_testing",
        "scenario_coverage",
        "security_testing",
    ):
        assert expected_check in checks


def test_phase11c_prompt_scope_excludes_reference_docs() -> None:
    validator = load_validator()
    prompt_paths = {str(path.relative_to(ROOT)) for path in validator.prompt_files()}
    assert "factory_governance/01_PROJECT_CHARTER.md" not in prompt_paths
    assert "factory_governance/templates/architecture_decision_record_template.v1.md" not in prompt_paths
    assert "docs/phase8_governed_multi_agent_role_simulation.md" not in prompt_paths


def test_phase11c_precise_conflict_detection_does_not_flag_negated_policy() -> None:
    validator = load_validator()
    text = (
        "Do not describe the whole generated application as strictly mock-only. "
        "Integration tests must cover primary application flows against mock/simulated "
        "ecosystem adapters and must not call live NPCI, RBI, bank, PSP, payment rail, "
        "customer, or production infrastructure. "
        "Do not bypass validation."
    )
    assert validator._conflicts(text) == []
