# Phase 13H — Release-State Lineage Registry

Phase 13H adds a deterministic release-state registry for the governed factory.

## Purpose

The registry gives operators a stable, machine-readable view of what has been completed, which tag is the trusted baseline, and which local commands remain safe to use.

## Truth boundary

- The default execution mode remains local deterministic.
- LangGraph/OpenAI execution remains detected and policy-gated; it is not falsely claimed as active.
- Release evidence avoids volatile timestamps and current-commit hashes, reducing validation-induced drift.
- Validators are treated as read-only gates after Phase 13G.

## Operator value

A reviewer can open the Phase 13H JSON snapshot or portal and quickly understand the completed milestone chain from Phase 13C through Phase 13G, the baseline tag for this phase, and the command surface available through `./factoryctl`.
