# Phase 11B Requirement Intake Contract

Labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- MIGRATION_SEAMS_ALLOWED
- DETERMINISTIC_VALIDATION_REQUIRED
- TRACEABILITY_REQUIRED
- QUALITY_GATES_REQUIRED

Phase 11B must classify payment-domain requirements before generation.

The intake decision must identify:
1. Whether the primary application can be generated as real local software.
2. Which surrounding ecosystem applications must be simulated.
3. Whether all data can remain synthetic.
4. Whether any external connectivity request must be rejected or converted.
5. Which payment capability pack and application archetype are required.
6. Which requirement gaps must be reported before code generation.

The factory must produce a generation contract only when the requirement is
safe, traceable, and compatible with the real-primary-app and simulated-
ecosystem boundary.
