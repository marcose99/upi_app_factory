# Phase 46H — Path-neutral runtime hardening

Phase 46H removes dependence on the current physical checkout path from active
identity contracts. Runtime code resolves the repository and state roots from
governed environment variables or repository markers.

## Boundaries

- The checkout directory is not renamed.
- The Git remote is not renamed.
- Historical evidence is not rewritten.
- Compatibility aliases remain active.
- No live provider or production action is enabled.

The canonical tokens are `${REPO_ROOT}` and `${STATE_ROOT}`. Absolute checkout
paths are rejected by the active path contract.
