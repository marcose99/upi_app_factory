# External Connectivity Fail-Closed Policy

Labels:
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN
- MIGRATION_SEAMS_ALLOWED
- DETERMINISTIC_VALIDATION_REQUIRED

The factory may generate adapter interfaces and migration seams. Those seams
must default to fail-closed behavior unless connected to local simulated
ecosystem applications.

The generated system must not include credentials, real payment endpoints,
real account data, real UPI handles, or calls to real payment institutions.

If a requirement asks for real external connectivity, the requirement intake
gate must reject that part or convert it into a simulated ecosystem boundary
with a documented gap.
