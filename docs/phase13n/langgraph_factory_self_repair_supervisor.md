# Phase 13N - LangGraph Factory Supervisor with Bounded Self-Repair

Phase 13N addresses the manual-iteration problem observed during Phase 13M.
The goal is to move from repeated human-authored repair scripts toward a
factory-level LangGraph supervisor that can diagnose a validation failure, apply
a bounded repair, rerun validation, and capture evidence.

## Scope

The Phase 13N graph is intentionally lightweight and local-first. It does not
require Kubernetes, queues, databases, or a distributed runtime. It does use a
real LangGraph `StateGraph`.

The graph contains:

- `plan_agent`;
- `validate_agent`;
- `diagnose_agent`;
- `repair_agent`;
- `proof_gate_agent`;
- `governance_evidence_agent`.

## Bounded repair policy

The supervisor is not an unlimited autonomous mutator. It is intentionally
bounded:

- maximum repair attempts are fixed;
- repair target is restricted to generated lifecycle evidence;
- proof commands must pass;
- governance evidence is written after completion.

## Boundary

The primary generated UPI dispute logic remains local and runnable. External
banks, rails, NPCI-style, RBI-style, upstream, and downstream interfaces remain
simulated mock boundaries.
