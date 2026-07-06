# Phase 13R - Governed Agentic Phase Runner

Phase 13R introduces a top-level LangGraph runner for phase execution.

## Why this exists

Earlier phases proved agentic generation, self-repair, operator handover, fresh
clone replay, and standalone recipient bootstrap. However, the outer phase loop
was still manually driven by generated shell scripts.

Phase 13R changes the operating model: one governed runner owns the phase loop.

## Runner agents

The runner is a LangGraph `StateGraph` with these governed nodes:

1. `preflight_agent`
2. `phase_plan_agent`
3. `implementation_agent`
4. `validation_agent`
5. `failure_diagnosis_agent`
6. `bounded_repair_agent`
7. `human_release_gate_agent`
8. `evidence_agent`

## Governance boundary

The runner may plan, generate, validate, diagnose, and bounded-repair changes
only inside approved file scopes.

The following remain blocked until explicit human approval:

- merge;
- tag;
- push;
- release publishing;
- destructive cleanup;
- real external ecosystem calls;
- production deployment.

## Mock ecosystem boundary

The primary generated UPI dispute lifecycle logic remains local and runnable.
External banks, rails, NPCI-style, RBI-style, upstream, and downstream ecosystem
interfaces remain simulated mock boundaries only.

## Example

```bash
python scripts/run_governed_agentic_phase.py \
  --objective "add next governed factory capability" \
  --phase-id phase13_next \
  --dry-run
```

The runner writes audit evidence and stops at the human release approval gate.

## Audit trail completeness

The `evidence_agent` action is recorded before audit JSON persistence. This ensures validators, reviewers, and release approvers see the complete agent action trail in the persisted evidence artifact.
