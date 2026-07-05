# Production-Quality Observability Policy — upi_dispute_resolution

Labels: PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED,
DETERMINISTIC_VALIDATION_REQUIRED, HUMAN_APPROVAL_REQUIRED

Generated applications and ecosystem mocks must expose production-grade
observability discipline while remaining lightweight locally.

Required telemetry concepts:

- structured JSON logs
- request_id, correlation_id, run_id, decision_id, and trace_id fields
- audit events for decisions and guardrail outcomes
- metrics for request counts, error counts, latency, retries, queue depth,
  worker counts, rejected work, duplicate work, and replay outcomes
- health, readiness, and liveness checks
- clear error taxonomy
- debug guide for local incident investigation
- production deployment observability document

Local output may be JSON log files and metrics snapshots. The design must include
adapters for later OpenTelemetry-compatible telemetry.
