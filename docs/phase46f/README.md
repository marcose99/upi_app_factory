# Phase 46F — Contract-First Bounded Display Migration

Phase 46F activates the canonical product-facing display identity **UPI App Factory** while preserving governed read compatibility for:

- `FactoryFromNothing`
- `UPI Dispute Resolution Factory`

The migration is deliberately bounded:

- new writes and product-facing output must use `UPI App Factory`;
- the two governed legacy display identities remain accepted as compatibility inputs;
- legacy aliases are not deleted;
- technical identifier migration remains deferred;
- the local checkout is not renamed;
- the remote repository is not renamed;
- historical evidence is not rewritten;
- generated applications are not mutated;
- no live provider, production deployment, tag, release, or LLM call occurs.

## Verification

```bash
./bin/upi-app-factory transform verify-display-identity-contract
./bin/upi-app-factory transform display-identity-status
```

## Lifecycle execution

Phase 46F is executed by the repository-native lifecycle orchestrator:

```bash
./bin/upi-app-factory lifecycle run phase46f   --approve commit,merge,push   --resume
```

The lifecycle engine owns exact candidate verification, secret scanning, validation, commit, fast-forward merge, main-only push, resume, and closure evidence.
