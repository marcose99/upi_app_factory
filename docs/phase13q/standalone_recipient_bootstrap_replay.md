# Phase 13Q - Standalone Recipient Bootstrap Replay

Phase 13Q closes the remaining handover gap from Phase 13P. Phase 13P proved a
fresh-clone replay while reusing the current Python environment. Phase 13Q proves
the recipient path using a fresh clone plus a newly-created recipient virtual
environment.

## Objective

Prove that a recipient can:

1. clone the finalized repository;
2. check out the finalized Phase 13P tag;
3. create a new local Python virtual environment;
4. install the lightweight recipient runtime from `requirements-recipient.txt`;
5. regenerate the Phase 13O operator pack;
6. run health check, lifecycle demo, verifier, and one-command demo.

## Runtime boundary

The bootstrap remains lightweight. It uses Python `venv`, LangGraph, Pytest, and
filesystem evidence. It does not require Kubernetes, real payment rails, real
bank integrations, NPCI-style systems, RBI-style systems, upstream systems, or
downstream systems.

## Pytest collection isolation

The fresh-clone bootstrap workspace is created outside the active repository
tree so repository-level full Pytest does not recursively collect the cloned
repository's own `tests/` package.

## Boundary

The primary generated UPI dispute lifecycle logic remains local and runnable.
External banks, rails, NPCI-style, RBI-style, upstream, and downstream ecosystem
interfaces remain simulated mock boundaries only.

## Static typing note

The replay runner annotates copied `BootstrapState` values explicitly so MyPy preserves the `TypedDict` type across state updates in the LangGraph workflow.
