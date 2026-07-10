# Phase 46N — Isolated Clean-Slate Replay and Handoff Proof

The replay harness creates a local no-hardlink clone, copies hash-pinned ignored
evidence, removes generated outputs only inside the sandbox, runs the governed
local generator, validates the portal/export flow, and packages handoff
evidence.

The live generated workspace is never deleted or replaced.
