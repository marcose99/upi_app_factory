# Phase 13AH — Clean-Slate Human Approval Workflow and Token Gate

## Purpose

Phase 13AH adds the human approval workflow needed before any future destructive clean-slate regeneration.

This phase is still **non-destructive**. It does not delete the generated application.

## Why this is required

A future clean-slate regeneration will eventually delete:

```text
workspace/factory_generated/upi_dispute_resolution/generated_application
```

That operation must require a valid human approval token. The token must prove that the approver understands:

- the target is limited to `generated_application`
- backup/restore planning is required
- lifecycle and release evidence must be preserved
- regenerated output must be fully revalidated
- release remains human-gated

## Required token schema

The approval token must use:

```text
clean-slate-human-approval.v1
```

The operation must be:

```text
CLEAN_SLATE_GENERATED_APPLICATION_REGENERATION
```

## Governance improvement introduced

Phase 13AF created a deletion boundary. Phase 13AG created a backup/restore/evidence plan. Phase 13AH adds explicit approval-token validation so that future destructive clean-slate regeneration cannot proceed by accident or through an ambiguous console command.
