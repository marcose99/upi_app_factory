#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"

AGENTIC_CONTRACT_MARKER = "FactoryFromNothing Agentic AI Best-Practice Contract"
GENERATED_APP_CONTRACT_MARKER = "Phase 11C Generated Application Type and Quality Contract"

BEST_PRACTICE_TERMS: dict[str, tuple[str, ...]] = {
    "agent_role_scope": ("agent role", "scope", "non-goals"),
    "input_output_contracts": ("input/output contracts", "contracts"),
    "deterministic_execution": ("deterministic", "reproducible"),
    "tool_governance": ("least-privilege", "tool"),
    "untrusted_input_security": ("prompt-injection", "untrusted-input"),
    "evidence_grounding": ("evidence", "provenance"),
    "privacy_security": ("PII", "secret"),
    "payments_boundary": (
        "real primary UPI/payment application with mock/simulated external ecosystem",
        "real, locally runnable software",
        "mock/simulated",
    ),
    "sdlc_best_practices": (
        "technology-specific SDLC best practices",
        "programming language",
        "framework",
    ),
    "observability_metrics_cost": (
        "observability",
        "LLM metrics",
        "expense ledgers",
    ),
    "generated_application_type_best_practices": (
        "generated application type",
        "UPI/payment dispute resolution application",
        "domain-appropriate architecture",
    ),
    "code_quality_reporting": (
        "code quality report",
        "lint results",
        "type-check results",
    ),
    "unit_testing": ("unit test report", "Unit tests must cover"),
    "integration_testing": ("integration test report", "Integration tests must cover"),
    "scenario_coverage": ("scenario coverage report", "Scenario coverage must map"),
    "security_testing": ("security review evidence", "unsafe output handling"),
    "resilience_recovery": ("retry", "timeout", "fail-closed"),
    "audit_release_governance": ("release-readiness evidence", "quality gate"),
    "final_metrics_last": (
        "final consolidated LLM metrics and expense summary",
        "no additional LLM calls are allowed",
    ),
}

CONFLICT_PATTERNS: dict[str, re.Pattern[str]] = {
    "mock_only_primary_app": re.compile(
        r"\bprimary\b.{0,80}\b(mock[- ]only|strictly mock|simulation-only)\b",
        re.IGNORECASE,
    ),
    "whole_app_mock_only": re.compile(
        r"\b(whole|entire)\b.{0,80}\b(application|generated application)\b.{0,80}\b(mock[- ]only|strictly mock|simulation-only)\b",
        re.IGNORECASE,
    ),
    "live_external_rails": re.compile(
        r"\b(call|connect to|integrate with)\b.{0,80}\b(live|production)\b.{0,80}\b(NPCI|RBI|bank|PSP|payment rail)\b",
        re.IGNORECASE,
    ),
    "disable_metrics": re.compile(
        r"\b(disable|skip|omit|do not record)\b.{0,60}\b(LLM metrics|expense ledger|call metrics)\b",
        re.IGNORECASE,
    ),
    "skip_all_validation": re.compile(
        r"\b(skip all validation|disable all validators|ignore all validation failures)\b",
        re.IGNORECASE,
    ),
    "ignore_security": re.compile(
        r"\b(ignore all security|disable all security|skip all security checks)\b",
        re.IGNORECASE,
    ),
}

NEGATION_HINTS: tuple[str, ...] = (
    "do not ",
    "must not ",
    "never ",
    "not ",
    "prohibit",
    "prohibited",
    "no live ",
    "remain mock",
)

EXCLUDED_PATH_PARTS: tuple[str, ...] = (
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
)

DOC_PROMPT_FILES: tuple[str, ...] = (
    "docs/agent_prompt_quality_guide.md",
    "docs/generated_application_quality_prompting_guide.md",
    "docs/prompt_quality_guide.md",
)

FACTORY_GOVERNANCE_PROMPT_FILES: tuple[str, ...] = (
    "factory_governance/00_SYSTEM_PROMPT.md",
    "factory_governance/03_AGENT_ROLE_PROMPTS.md",
)

BASELINE_PROMPT_FILE_NAMES: tuple[str, ...] = (
    "00_SYSTEM_PROMPT.md",
    "03_AGENT_ROLE_PROMPTS.md",
)

INCLUDED_WORKSPACE_PROMPTS: tuple[str, ...] = (
    "technology_specific_prompt_instructions.md",
    "prompt_injection_and_untrusted_input_policy.md",
    "phase11b_prompt_enhancement_contract.md",
)


def _is_excluded(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    return any(part in EXCLUDED_PATH_PARTS for part in rel_parts)


def is_prompt_source_file(path: Path) -> bool:
    if path.suffix.lower() not in {".md", ".txt"}:
        return False

    if _is_excluded(path):
        return False

    rel = path.relative_to(ROOT).as_posix()

    if rel.startswith("prompts/"):
        return True

    if rel in DOC_PROMPT_FILES:
        return True

    if rel in FACTORY_GOVERNANCE_PROMPT_FILES:
        return True

    if rel.startswith("factory_governance/agent_prompts/"):
        return True

    if (
        rel.startswith("factory_governance/baseline_original/")
        and path.name in BASELINE_PROMPT_FILE_NAMES
    ):
        return True

    if "/lifecycle_artifacts/" in rel and path.name in INCLUDED_WORKSPACE_PROMPTS:
        return True

    return False


def prompt_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if is_prompt_source_file(path))


def _contains_all_terms(text: str, terms: tuple[str, ...]) -> bool:
    return all(term in text for term in terms)


def _is_negated_context(text: str, start: int) -> bool:
    prefix = text[max(0, start - 120):start].lower()
    return any(hint in prefix for hint in NEGATION_HINTS)


def _conflicts(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for conflict_id, pattern in CONFLICT_PATTERNS.items():
        for match in pattern.finditer(text):
            if _is_negated_context(text, match.start()):
                continue
            start = max(match.start() - 80, 0)
            end = min(match.end() + 80, len(text))
            snippet = " ".join(text[start:end].split())
            found.append({"conflict_id": conflict_id, "snippet": snippet})
            break
    return found


def validate() -> dict[str, Any]:
    files = prompt_files()
    errors: list[dict[str, Any]] = []

    for prompt_file in files:
        text = prompt_file.read_text(encoding="utf-8")
        file_errors: list[str] = []

        if AGENTIC_CONTRACT_MARKER not in text:
            file_errors.append("missing_agentic_ai_best_practice_contract_section")

        if GENERATED_APP_CONTRACT_MARKER not in text:
            file_errors.append("missing_generated_application_quality_contract_section")

        for check_name, terms in BEST_PRACTICE_TERMS.items():
            if not _contains_all_terms(text, terms):
                file_errors.append(f"missing_best_practice_terms:{check_name}")

        conflicts = _conflicts(text)

        if file_errors or conflicts:
            errors.append(
                {
                    "path": str(prompt_file.relative_to(ROOT)),
                    "errors": file_errors,
                    "conflicts": conflicts,
                }
            )

    return {
        "passed": not errors and bool(files),
        "phase": "Phase 11C",
        "app_id": APP_ID,
        "prompt_files_checked": len(files),
        "checks_per_prompt": len(BEST_PRACTICE_TERMS),
        "conflict_patterns_checked": len(CONFLICT_PATTERNS),
        "errors": errors,
        "reference_baseline": [
            {
                "name": "OpenAI Agents SDK",
                "reason": "Agent runs, tools, handoffs, guardrails, sessions, and multi-step application structure.",
                "url": "https://developers.openai.com/api/docs/guides/agents",
            },
            {
                "name": "OWASP Top 10 for LLM Applications",
                "reason": "Prompt injection, insecure output handling, excessive agency, data leakage, and other LLM application risks.",
                "url": "https://owasp.org/www-project-top-10-for-large-language-model-applications/",
            },
            {
                "name": "NIST AI Risk Management Framework",
                "reason": "Govern, map, measure, and manage trustworthy AI risks through the AI system lifecycle.",
                "url": "https://www.nist.gov/itl/ai-risk-management-framework",
            },
            {
                "name": "pytest",
                "reason": "Unit and scenario tests using fixtures and parametrization.",
                "url": "https://docs.pytest.org/en/stable/",
            },
        ],
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
