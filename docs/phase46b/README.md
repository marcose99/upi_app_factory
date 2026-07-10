# Phase 46B — Governed Deterministic Execution

Phase 46B introduces the first mutation-capable autonomous execution layer.

The initial approved catalog is deliberately narrow:

- current product display branding only;
- deterministic exact-string replacements;
- no technical namespace migration;
- no generated-application mutation;
- no historical-evidence mutation;
- no LLM calls;
- no commit, merge, tag, push, release, checkout rename, or repository rename.

Every run creates:

- an immutable candidate plan;
- a backup archive and manifest before mutation;
- hash-chained checkpoints;
- an append-only event ledger;
- full validation evidence;
- bounded automatic rollback on validation failure;
- a replayable review bundle.

Commands:

```bash
./bin/upi-app-factory transform execute --mode rehearsal
./bin/upi-app-factory transform execute --mode apply-safe
./bin/upi-app-factory transform execution-status
./bin/upi-app-factory transform replay --run-id <run-id>
```

