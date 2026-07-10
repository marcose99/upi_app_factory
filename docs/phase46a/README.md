# Phase 46A — Deterministic Autonomous Transformation Foundation

Run from this worktree:

```bash
./bin/upi-app-factory transform plan
./bin/upi-app-factory transform status
```

The workflow performs a read-only repository inventory and produces its state
under `UPI_APP_FACTORY_STATE_DIR`, or the XDG state directory when the variable
is not configured.

Review bundles are written under `UPI_APP_FACTORY_EXPORT_DIR`, or the XDG data
directory when the variable is not configured.

The workflow performs zero LLM calls and no commit, merge, tag, push, release,
physical checkout rename, or remote repository rename.
