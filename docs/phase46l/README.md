# Phase 46L — Declarative Repair Policy Engine

This phase moves repair authorization from imperative code into a versioned
repair catalog and policy evaluator.

Automatic repairs remain limited to deterministic low-risk operations.
Unknown semantic failures fail closed and produce incident evidence.

Protected release, tag, deployment, namespace retirement, and security-policy
changes remain human-approved.
