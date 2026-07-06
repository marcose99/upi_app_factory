#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_LLM_CALL_METRIC_FIELDS: tuple[str, ...] = (
    "call_id",
    "build_id",
    "phase",
    "agent_name",
    "prompt_file",
    "prompt_version_or_hash",
    "model_provider",
    "model_name",
    "request_started_at_utc",
    "response_completed_at_utc",
    "latency_ms",
    "status",
    "error_type",
    "retry_attempt",
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "total_tokens",
    "tool_call_count",
    "tool_names",
    "temperature",
    "top_p",
    "max_output_tokens",
    "pricing_config_version",
    "input_token_unit_price",
    "output_token_unit_price",
    "calculated_call_cost",
    "currency",
    "purpose",
    "requirement_ids_touched",
    "generated_artifacts_touched",
)

FINAL_LLM_METRICS_EXPENSE_ARTIFACTS: tuple[str, ...] = (
    "llm_call_metrics_ledger.jsonl",
    "llm_call_expense_ledger.jsonl",
    "llm_metrics_summary.json",
    "llm_expense_summary.json",
    "llm_metrics_and_expense_report.md",
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


def required_terms() -> list[str]:
    return (
        list(REQUIRED_LLM_CALL_METRIC_FIELDS)
        + list(FINAL_LLM_METRICS_EXPENSE_ARTIFACTS)
        + [
            "no additional LLM calls are allowed",
            "real, locally runnable software",
            "mock/simulated",
        ]
    )


def validate() -> dict[str, Any]:
    missing_by_file: dict[str, list[str]] = {}
    files = prompt_files()

    for prompt_file in files:
        text = prompt_file.read_text(encoding="utf-8")
        missing = [term for term in required_terms() if term not in text]
        if missing:
            missing_by_file[str(prompt_file.relative_to(ROOT))] = missing

    return {
        "passed": not missing_by_file and bool(files),
        "prompt_files_checked": len(files),
        "errors": [
            f"{path} missing: {', '.join(missing)}"
            for path, missing in missing_by_file.items()
        ],
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
