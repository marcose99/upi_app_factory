from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase11c_agentic_prompt_best_practices.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "phase11c_agentic_prompt_validator", VALIDATOR_PATH
    )
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


def test_prompt_include_syntax_resolves_shared_contract_files(tmp_path: Path) -> None:
    validator = load_validator()
    contract_dir = tmp_path / "prompts" / "_contracts"
    contract_dir.mkdir(parents=True)
    contract_path = contract_dir / "agentic_ai_best_practice_contract.md"
    contract_path.write_text(
        "UPI App Factory Agentic AI Best-Practice Contract\n", encoding="utf-8"
    )
    prompt_path = tmp_path / "prompts" / "phase99" / "prompt.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}\n",
        encoding="utf-8",
    )

    resolved = validator.resolve_prompt_includes(prompt_path, root=tmp_path)

    assert "UPI App Factory Agentic AI Best-Practice Contract" in resolved


def test_missing_prompt_include_target_fails_safely(tmp_path: Path) -> None:
    validator = load_validator()
    prompt_path = tmp_path / "prompts" / "phase99" / "prompt.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "{{ include: prompts/_contracts/missing_contract.md }}\n",
        encoding="utf-8",
    )

    try:
        validator.resolve_prompt_includes(prompt_path, root=tmp_path)
    except validator.PromptIncludeError as exc:
        assert "Missing prompt include target" in str(exc)
    else:
        raise AssertionError("missing include target did not fail")


def test_phase11c_best_practice_validator_uses_resolved_prompt_text() -> None:
    validator = load_validator()
    phase28_prompt = ROOT / "prompts/phase28/generated_application_architecture_depth_prompt.md"
    raw_text = phase28_prompt.read_text(encoding="utf-8")
    resolved_text = validator.resolve_prompt_includes(phase28_prompt, root=ROOT)

    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in raw_text
    assert validator.AGENTIC_CONTRACT_MARKER in resolved_text
    assert validator.GENERATED_APP_CONTRACT_MARKER in resolved_text
    for terms in validator.BEST_PRACTICE_TERMS.values():
        assert validator._contains_all_terms(resolved_text, terms)


def test_phase28_prompt_inherits_shared_contracts_without_repair_blocks() -> None:
    validator = load_validator()
    phase28_prompt = ROOT / "prompts/phase28/generated_application_architecture_depth_prompt.md"
    raw_text = phase28_prompt.read_text(encoding="utf-8")
    resolved_text = validator.resolve_prompt_includes(phase28_prompt, root=ROOT)

    assert "PHASE28_REPAIR_AGENTIC_BEST_PRACTICE_AND_LLM_METRICS_CONTRACT_V1" not in raw_text
    assert "PHASE28_PROMPT_GOVERNANCE_REPAIR_V2_EXACT_MARKERS" not in raw_text
    assert "PHASE28_V3_CANONICAL_PHASE11C_PROMPT_CONTRACT_REPAIR" not in raw_text
    assert "UPI App Factory Agentic AI Best-Practice Contract" in resolved_text
    assert "Phase 11C Generated Application Type and Quality Contract" in resolved_text
    assert "Mandatory every-LLM-call metrics and expense evidence" in resolved_text


def test_phase11c_prompt_scope_excludes_reference_docs() -> None:
    validator = load_validator()
    prompt_paths = {str(path.relative_to(ROOT)) for path in validator.prompt_files()}
    assert "factory_governance/01_PROJECT_CHARTER.md" not in prompt_paths
    assert (
        "factory_governance/templates/architecture_decision_record_template.v1.md"
        not in prompt_paths
    )
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
