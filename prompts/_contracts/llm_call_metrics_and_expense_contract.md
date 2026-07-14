## Mandatory every-LLM-call metrics and expense evidence

This prompt is governed by the UPI App Factory LLM metrics and expense policy.

For every LLM/model call made while executing this prompt, the agent/factory MUST record one complete call-level metrics event and one complete expense event. The records MUST be append-only, evidence-grade, and traceable to the build, phase, agent, prompt, requirements, generated artifacts, model, retry attempt, token usage, tool usage, and pricing configuration.

Each LLM call metrics record MUST include all of these fields:

- `call_id`
- `build_id`
- `phase`
- `agent_name`
- `prompt_file`
- `prompt_version_or_hash`
- `model_provider`
- `model_name`
- `request_started_at_utc`
- `response_completed_at_utc`
- `latency_ms`
- `status`
- `error_type`
- `retry_attempt`
- `input_tokens`
- `output_tokens`
- `cached_input_tokens`
- `reasoning_tokens`
- `total_tokens`
- `tool_call_count`
- `tool_names`
- `temperature`
- `top_p`
- `max_output_tokens`
- `pricing_config_version`
- `input_token_unit_price`
- `output_token_unit_price`
- `calculated_call_cost`
- `currency`
- `purpose`
- `requirement_ids_touched`
- `generated_artifacts_touched`

The required consolidated metrics and expense artifacts are:

- `llm_call_metrics_ledger.jsonl`
- `llm_call_expense_ledger.jsonl`
- `llm_metrics_summary.json`
- `llm_expense_summary.json`
- `llm_metrics_and_expense_report.md`

The final consolidated LLM metrics and expense summary MUST be the last LLM-dependent artifact. After `llm_metrics_summary.json`, `llm_expense_summary.json`, and `llm_metrics_and_expense_report.md` are emitted, no additional LLM calls are allowed for the same build. Any additional LLM call requires a new build/run and a new metrics/expense ledger sequence.

The generated primary payment/UPI application remains real, locally runnable software. Only external ecosystem applications, rails, banks, NPCI/RBI interfaces, upstream/downstream integrations, and third-party dependencies are mock/simulated unless explicitly brought in scope.
