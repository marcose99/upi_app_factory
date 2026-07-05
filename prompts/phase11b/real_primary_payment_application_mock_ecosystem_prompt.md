# Phase 11B Prompt Boundary: Real Primary Payment Application, Mock Ecosystem

The generated primary payment-domain application must be real local software:
APIs, contracts, models, workflows, validation, persistence boundaries,
observability hooks, tests, and evidence must be functioning implementation
assets.

The surrounding ecosystem must be simulated:
banks, PSPs, payment rails, merchant systems, customer notification systems,
fraud scoring systems, ledger sources, reconciliation sources, and external
payment dependencies are represented by local simulated ecosystem applications.

Required labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN
- MIGRATION_SEAMS_ALLOWED
- DETERMINISTIC_VALIDATION_REQUIRED
- TRACEABILITY_REQUIRED
- QUALITY_GATES_REQUIRED

Never generate real payment connectivity, real credentials, real customer data,
or unsupported certification/readiness claims. Migration seams are allowed only
as fail-closed interfaces until connected to local simulated ecosystem services.
