# Phase 13P - Fresh Clone Handover Replay

Phase 13P validates the operator handover flow from a fresh clone of the
finalized Phase 13O tag.

## Objective

Prove that a recipient can start from the finalized repository tag, regenerate
the local operator handover pack, and run the local UPI dispute lifecycle demo.

## Replay scope

The replay performs these steps:

1. clone the repository into an isolated replay workspace;
2. check out `v0.13.14-local-runnable-operator-demo-pack`;
3. run the Phase 13O operator packager in the clone;
4. run the Phase 13O validator in the clone;
5. run health check, local lifecycle demo, verifier, and one-command demo.

## Runtime note

The default replay mode reuses the current Python virtual environment while
executing against the fresh clone source tree. This avoids introducing network
or dependency-install flakiness while still proving clean-clone source replay.

## Boundary

The primary generated UPI dispute lifecycle logic remains local and runnable.
External banks, rails, NPCI-style, RBI-style, upstream, and downstream ecosystem
interfaces remain simulated mock boundaries only.

## Pytest collection isolation

The fresh-clone replay workspace is created outside the active repository tree so repository-level full Pytest does not recursively collect the cloned repository's own `tests/` package.
