# Phase 13I — Release Readiness and Operator Acceptance

Phase 13I adds a deterministic release-readiness gate for the governed local factory.

## Purpose

This phase gives an operator a single auditable answer to this question:

> Is the current factory release ready to be handed to another person for local execution?

## Acceptance Gates

A release is accepted only when all of the following are true:

1. Phase 13C to Phase 13H release tags are present.
2. The `factoryctl` operator command exists.
3. `factoryctl status`, `factoryctl adapters`, and `factoryctl handover` smoke checks pass.
4. `factoryctl handover` has no `[MISSING]` entries.
5. Required operator, adapter, handover, drift-guardrail, and lineage files exist.
6. The truth boundary is preserved.

## Truth Boundary

Local deterministic execution remains the default. LangGraph/OpenAI execution remains detected and policy-gated. This phase does not activate networked or LLM-backed agent execution.

## Operator Commands

```bash
./factoryctl status
./factoryctl adapters
./factoryctl validate --quick
./factoryctl handover
./factoryctl logs
```
