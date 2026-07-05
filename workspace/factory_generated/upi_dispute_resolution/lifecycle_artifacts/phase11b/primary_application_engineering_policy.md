# Primary Application Engineering Policy

Labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- SYNTHETIC_DATA_ONLY
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN
- DETERMINISTIC_VALIDATION_REQUIRED
- TRACEABILITY_REQUIRED
- QUALITY_GATES_REQUIRED

The primary payment application must be generated as real local software.
It must include functioning APIs, domain models, validation, workflow logic,
persistence abstractions, audit events, structured logs, tests, and evidence.

The primary application must use synthetic data only. It must not process real
payments, use real customer information, or make external payment-network calls.

The correct positioning is: real local primary payment application, simulated
ecosystem, synthetic data, deployment planning, migration seams, deterministic
validation, and audit-friendly evidence.
