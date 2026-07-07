# Phase 13X — Agent Runtime Abstraction Layer

Phase 13X introduces a factory-owned agent runtime abstraction so the governed factory core is not permanently coupled to LangGraph or any other single agent framework.

## Principle

The factory core owns governance concepts: requirement packages, policies, traceability, audit evidence, validation gates, bounded repair rules, human approval gates, and mock ecosystem boundaries.

Agent frameworks provide orchestration mechanics only: nodes, edges, state passing, routing, and execution.

## Runtime boundary

Factory Core -> AgentRuntimePort -> Runtime Adapter

Current adapters:

- deterministic adapter: local deterministic execution proof
- langgraph adapter: current LangGraph `StateGraph` orchestration proof

Future adapters may include OpenAI Agents SDK, CrewAI, AutoGen, Semantic Kernel, Temporal-backed workflows, or an in-house deterministic runtime.

## Governance lesson

Framework-specific behavior, such as LangGraph runtime type-hint evaluation, must remain outside the factory core. Tests that dynamically load modules must register modules in `sys.modules` before runtime type-hint evaluation.

## LLM mode

This phase uses deterministic local execution. No OpenAI key is required. Future LLM mode must use external secret injection and must produce prompt, response, model, token/cost, policy, and traceability evidence.

## JSON loader typing and annotated tag verification

Phase 13X records two governance hardening lessons:

- JSON loader helpers that declare `dict[str, Any]` must cast `json.loads(...)`
  return values explicitly so strict MyPy does not leak `Any` through factory
  validation utilities.
- Release automation must verify annotated Git tags using dereferenced tag
  commits such as `refs/tags/<tag>^{}` rather than pseudo remote paths such as
  `origin/tags/<tag>`.

These checks protect the factory from framework/runtime drift and release proof
ambiguity while preserving the agent runtime abstraction boundary.
