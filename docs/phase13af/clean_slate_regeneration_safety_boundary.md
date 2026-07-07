# Phase 13AF — Clean-Slate Regeneration Safety Boundary and Deletion Guard

## Purpose

The final factory goal includes deleting the already generated application and regenerating a fresh governed UPI dispute-resolution application from scratch.

That action is powerful and must not be introduced casually. Phase 13AF establishes the safety boundary before any destructive clean-slate regeneration is allowed.

## Phase 13AF decision

Phase 13AF is **non-destructive**.

It introduces:

- allowed generated-application deletion boundary
- blocked deletion paths
- symlink rejection
- backup requirement
- evidence-preservation requirement
- dry-run deletion plan
- audit record
- human approval requirement
- future regeneration readiness rule

## Allowed delete target

Only this path is eligible for a future clean-slate delete operation:

```text
workspace/factory_generated/upi_dispute_resolution/generated_application
```

## Blocked delete targets

The guard must reject:

- repository root
- `.git`
- `.venv`
- `docs`
- `policies`
- `scripts`
- `tests`
- `factory_governance`
- lifecycle artifacts
- release/handoff evidence
- paths outside the project root
- symlinks
- home directory or filesystem root

## Governance improvement introduced

This phase prevents unsafe clean-slate regeneration. Before the factory is allowed to delete and regenerate the application, it must first prove what will be deleted, what will be preserved, what backup will exist, and what human approval is required.

This strengthens the final clean-slate regeneration objective without introducing destructive behavior yet.
