# Persistence And Reset Policy

The generated application remains local-first, deterministic-first, and
mock-only.

## Durable State

- SQLite runtime state remains inside the generated application state root.
- Audit-chain records remain append-only under the local deterministic runtime.
- Exact-v2 evidence artifacts are repository-owned validation evidence and are
  rematerialized deterministically.

## Reset Rules

- Reset operations apply only to disposable local demonstration state.
- Deterministic evidence regeneration must not require external network access.
- Runtime execution must not mutate tracked source files.

## Non-Claims

- No live payment-rail, bank, PSP, NPCI, or identity-provider state is stored.
- This policy does not claim production retention, regulatory approval, or
  certification.
