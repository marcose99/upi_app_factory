# Phase 13K — Release Handoff Replay Verification

Phase 13K verifies that the Phase 13J release handoff bundle can be replayed locally by another operator.

## Truth boundary

The replay remains local deterministic. It does not activate LangGraph or OpenAI execution. External adapters remain detected and policy-gated, not falsely claimed as active.

## Important checksum rule

The Phase 13J `CHECKSUMS.sha256` file describes repository-root release files. Phase 13K therefore validates those checksum entries against the repository root. The bundle directory itself is separately checked for its required handoff files.

## Replay checks

- Baseline tag `v0.13.9-release-handoff-bundle-pack` exists.
- Handoff bundle files exist.
- Checksum manifest entries match repository-root files.
- Operator commands are documented.
- `./factoryctl status`, `./factoryctl adapters`, and `./factoryctl handover` replay successfully.
- `./factoryctl handover` has no `[MISSING]` entries.
