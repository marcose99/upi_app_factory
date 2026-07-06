# Phase 13C Agent Runtime Handover

## Purpose

This document is the canonical operator handover for the real local governed
agent-runtime foundation introduced in Phase 13C and used by later Phase 13D,
Phase 13E, and Phase 13F operator workflows.

## Truth boundary

The current runtime is a local deterministic governed runtime foundation. It
contains registries, ledgers, snapshots, self-correction governance, adapter
capability detection, portals, validators, and operator commands. It does not
claim that LangGraph or OpenAI-agent LLM execution is active by default.

Default execution remains local, deterministic, offline-friendly, and
safe-by-default. LangGraph and OpenAI execution paths must be explicitly
detected, policy-gated, approved, configured, and validated before use.

## Operator command surface

Use the Phase 13E operator CLI from the repository root:

```bash
./factoryctl status
./factoryctl adapters
./factoryctl validate --quick
./factoryctl validate
./factoryctl portals
./factoryctl handover
./factoryctl logs
```

## Runtime areas to know

- `src/factory_agent_runtime/` contains the governed runtime foundation and
  adapter execution layer.
- `docs/phase13c/` contains runtime foundation and self-correction governance
  documentation.
- `docs/phase13d/` contains adapter execution policy and architecture.
- `docs/phase13e/` contains the operator CLI command surface documentation.
- `workspace/factory_generated/upi_dispute_resolution/audit_portal/` contains
  generated local audit portals.
- `workspace/factory_generated/upi_dispute_resolution/run_logs/` contains local
  run logs when scripts are executed.

## Minimum validation before handover

Run:

```bash
./factoryctl validate --quick
./factoryctl handover
```

The handover command should not show missing required documents. Phase 13F adds
a dedicated audit to enforce that closure.

## Safe operating rule

When in doubt, run the deterministic local validation path first. Do not enable
networked or secret-backed execution until the policy gate, approval evidence,
secrets handling, and adapter-specific tests are present.
