# Phase 11B — Real Primary Application with Mock Ecosystem Boundary

Phase 11B establishes the corrected generation boundary for the payment-domain
factory.

The primary payment application is generated as real local software. The
external ecosystem is simulated.

This means:
- real local APIs, domain models, validation, workflows, tests, observability,
  and audit evidence for the primary application
- simulated banks, PSPs, rails, merchant systems, ledgers, notifications, fraud
  scoring, reconciliation sources, and other surrounding dependencies
- synthetic data only
- fail-closed external connectivity seams
- no real payment processing
- no unsupported certification/readiness claims

This boundary is the foundation for requirement intake, payment capability
classification, and future application generation.
