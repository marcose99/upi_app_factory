# Phase 13AK — Clean-Slate Regeneration Sandbox Rehearsal

## Purpose

Phase 13AK rehearses the future clean-slate regeneration workflow inside a quarantined sandbox.

It is still not the real clean-slate regeneration. It does not delete the real generated application and it does not overwrite the real generated application.

## Sandbox boundary

Allowed sandbox root:

```text
workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ak/sandbox
```

Protected real generated application path:

```text
workspace/factory_generated/upi_dispute_resolution/generated_application
```

## What this phase proves

The sandbox rehearsal proves:

1. The future clean-slate workflow can be planned from the Phase 13AJ dry-run harness.
2. Sandbox writes are isolated under Phase 13AK lifecycle artifacts.
3. The real generated application remains untouched.
4. Sandbox rehearsal output is manifestable and digestible.
5. Live provider calls and external system calls remain blocked.
6. Merge, tag, and release remain human-gated.

## Governance improvement introduced

Phase 13AJ planned the future workflow. Phase 13AK rehearses the workflow in a safe sandbox before touching the real generated application. This is an important bridge toward final clean-slate regeneration because it validates path isolation and evidence generation without destructive behavior.
