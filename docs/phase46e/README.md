# Phase 46E — Unified Governed Lifecycle Orchestrator

Phase 46E replaces one-off review, commit, merge, validation, push, and closure scripts with one repository-native lifecycle engine.

## Operating model

A phase is described by a declarative JSON manifest. The lifecycle engine runs the manifest through a durable state machine:

1. `PREFLIGHT_PASSED`
2. `WORKTREE_READY`
3. `IMPLEMENTED`
4. `TARGETED_VALIDATED`
5. `CANDIDATE_VERIFIED`
6. `FULLY_VALIDATED`
7. `POST_RESTORE_VALIDATED`
8. `COMMITTED`
9. `MERGED`
10. `PUSHED`
11. `CLOSED`

Each completed state produces SHA-256-protected evidence under:

```text
~/.local/state/upi_app_factory/lifecycle_runs/<run-id>/
```

The same command resumes an interrupted lifecycle run:

```bash
./bin/upi-app-factory lifecycle run phase46f \
  --approve commit,merge,push \
  --resume
```

## Governance

- Commit, merge, and push require explicit one-time approval at launch.
- Merge is fast-forward only.
- Only the base branch is pushed.
- Feature branches are not pushed.
- Tag, release, repository rename, production deployment, and live-provider enablement remain outside this automation.
- LLM calls are prohibited in deterministic lifecycle execution.
- Candidate paths must exactly match the manifest.
- High-confidence secret patterns fail closed.

## Validation

Validation gates use command exit status as the primary decision.

Observed test and source-file counts are retained as evidence but are not hardcoded pass/fail constants. A legitimate increase from 825 to 826 tests therefore remains a passing result when the command exits successfully.

## Incident replay coverage

Tests preserve the lessons from Phase 46D:

- increased test counts do not cause false failures;
- `checkpoint_verification.json` is not treated as a numbered checkpoint;
- generated Python is validated before atomic replacement;
- resume after local merge but before push is recognized;
- resume after remote synchronization is recognized.

## Manifest status

`config/lifecycle/phases/phase46f.draft.json` is intentionally `DRAFT`. It documents the next phase but cannot execute until its implementation command and exact candidate paths are finalized and the status is changed to `ACTIVE`.
