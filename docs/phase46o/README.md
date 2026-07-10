# Phase 46O — Authoritative Lifecycle Run Resolution

Phase 46O adds a read-only, fail-closed resolver for lifecycle runs.

A newer failed duplicate must not hide an older valid CLOSED run. The resolver
validates lifecycle completion, evidence hashes, manifest identity, Git
ancestry, protected-action boundaries, tag/release posture, and zero LLM calls.

The resolver does not mutate, move, delete, quarantine, repair, resume, commit,
merge, push, tag, or release any lifecycle run. Conflicting valid CLOSED
identities fail closed.

Integration into campaign and supervisor control flow is intentionally deferred
until this capability is independently validated.

Certification-ready evidence posture only. No certification claim is made.
