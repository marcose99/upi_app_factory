# Phase 13AE — Governed Self-Healing Adoption Gate for Future Phase Scripts

## Purpose

Phase 13AD introduced a reusable governed phase-runner integration harness. Phase 13AE adds an adoption gate so future phase automation cannot quietly return to ad hoc repair behavior.

## Rule

Every future phase automation script must either:

1. Use the governed phase runner, or
2. Declare an equivalent governed control using the marker `GOVERNED_SELF_HEALING_EQUIVALENT_CONTROL`.

An equivalent control must document:

- failure classification
- unknown-failure human escalation
- post-repair gate re-run
- audit evidence
- human approval boundaries

## Blocked behavior

The adoption gate rejects scripts that show bypass patterns such as:

- skipping MyPy
- skipping Ruff
- skipping pytest
- ignoring governance
- auto-approving release
- disabling policy
- bypassing gates

## Governance improvement introduced

This phase is a small but important governance improvement. Phase 13AD made the runner available; Phase 13AE makes runner adoption enforceable.

That strengthens quality across future factory elements because each new phase script must prove that governed self-healing is present or explicitly document equivalent controls.
