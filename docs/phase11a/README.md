# Phase 11A — Governed Agentic Code Generation Harness

Phase 11A prepares the governed agentic code-generation harness before the
first agent-generated implementation.

It creates:

- agentic_generation_harness_manifest.json
- agent_role_catalog.json
- agent_tool_contracts.json
- agent_state_schema.json
- agent_execution_policy.md
- agent_prompt_registry.json
- agent_deterministic_shadow_run.json
- proposed_generation_plan.json
- phase11b_entry_criteria.md
- phase11a_validation_report.json

Run:

```bash
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python scripts/run_phase11a_agentic_generation.py
python scripts/validate_phase11a_agentic_generation.py
```

Boundary:

- deterministic shadow mode first
- no LLM calls by default
- no network calls by default
- no implementation files written in Phase 11A
- no direct commit/merge/tag/push by agents
- human approval required for protected writes
- deterministic validation required before release
