# Mock Ecosystem Boundary Policy

Labels:
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- MIGRATION_SEAMS_ALLOWED
- TRACEABILITY_REQUIRED

Only the surrounding ecosystem applications are simulated.

Examples:
- bank simulator
- payment-rail simulator
- PSP simulator
- merchant simulator
- customer-notification simulator
- ledger simulator
- reconciliation-source simulator
- fraud-score simulator
- audit-evidence sink

These simulated ecosystem applications may support success, rejection,
timeout, delay, duplicate, retry, failover, and recovery scenarios. They must
clearly mark all responses as synthetic or simulated.
