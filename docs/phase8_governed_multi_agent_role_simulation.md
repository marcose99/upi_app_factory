# Phase 8: Governed Multi-Agent Role Simulation

## Purpose

Phase 8 converts the governed prompt pack into a deterministic role-agent
simulation.  It does not call an LLM.  The purpose is to prove the factory can
load role-agent prompts, execute a controlled agent sequence, record decisions,
record handoffs, emit audit events, and validate every agent output before real
LLM/tool execution is introduced.

## Why this phase exists

The factory should not move directly from prompts to autonomous agents.  It must
first prove the following capabilities in a deterministic and debug-friendly way:

1. Every required agent has a governed prompt.
2. Every agent output has requirement, task, policy, and evidence links.
3. Every handoff is recorded.
4. Every decision is recorded.
5. Every run emits validation evidence.
6. Honesty labels and mock boundaries remain visible.
7. Missing official sources are not hidden.

## New run workspace

Phase 8 writes agent runs under:

```text
workspace/agent_runs/<run_id>/
```

Each run produces:

```text
agent_run_manifest.json
agent_execution_plan.json
agent_outputs.jsonl
agent_decisions.jsonl
agent_handoffs.jsonl
agent_validation_report.json
agent_audit_events.jsonl
```

## Commands

Run a deterministic multi-agent simulation:

```bash
python scripts/run_multi_agent_factory_simulation.py --run-id manual_agent_run --force
```

Validate a specific run:

```bash
python scripts/validate_multi_agent_run.py --run-dir workspace/agent_runs/manual_agent_run
```

Validate the latest agent run:

```bash
make validate-agent-run
```

Run a default manual simulation:

```bash
make run-multi-agent-simulation
```

## Current limitation

Phase 8 is intentionally deterministic.  It does not perform autonomous LLM
execution, tool calling, external API calls, or official UPI rule lookup.  Those
capabilities should come later after workflow checkpoints, stronger security
controls, and human approval gates are added.
