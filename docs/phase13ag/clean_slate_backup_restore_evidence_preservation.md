# Phase 13AG — Clean-Slate Backup, Restore, and Evidence Preservation Plan

## Purpose

Phase 13AF established that generated-application deletion must be guarded. Phase 13AG adds the next foundation: a non-destructive backup, restore, and evidence-preservation plan.

This is required before any future clean-slate regeneration can delete the generated application.

## Phase 13AG decision

Phase 13AG remains **non-destructive**.

It adds a deterministic planner that can produce:

- source file manifest
- file hashes
- total byte count
- manifest digest
- backup target path
- restore target path
- evidence-preservation paths
- audit JSON

## Evidence preservation

Clean-slate regeneration must not destroy lifecycle or release evidence. These paths must be preserved:

```text
workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts
workspace/factory_generated/upi_dispute_resolution/release_handoff
```

## Governance improvement introduced

This phase ensures that clean-slate regeneration has a rollback foundation. Before deletion is allowed in a future phase, the factory must be able to describe what exists, where it will be backed up, how it would be restored, and which evidence must survive.

No generated application files are deleted in Phase 13AG.
