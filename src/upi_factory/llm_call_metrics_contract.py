"""LLM call metrics and expense contract for governed factory runs.

The primary payment/UPI application is generated as real, locally runnable
software. External ecosystem applications and integrations remain
mock/simulated unless explicitly brought in scope.
"""

from __future__ import annotations

from collections.abc import Mapping


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


def missing_llm_call_metric_fields(
    record: Mapping[str, object],
) -> list[str]:
    """Return required LLM call metric fields absent from a record."""

    return [
        field
        for field in REQUIRED_LLM_CALL_METRIC_FIELDS
        if field not in record
    ]


def has_complete_llm_call_metric_record(
    record: Mapping[str, object],
) -> bool:
    """Return True when a ledger record contains every required field."""

    return not missing_llm_call_metric_fields(record)


def final_metrics_summary_must_be_last_llm_dependent_artifact() -> str:
    """Return the non-negotiable final-artifact ordering rule."""

    return (
        "The final consolidated metrics and expense summary must be "
        "the last LLM-dependent artifact. No additional LLM calls are "
        "allowed "
        "after the final metrics and expense summary is emitted."
    )
