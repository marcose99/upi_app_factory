# Failure Mode Evidence

Wave D generated tests exercise these local-only cases:

- Startup applies migrations and exposes distinct `/startup`, `/live` and
  `/ready` contracts.
- Drain disables readiness and application traffic while keeping liveness
  available for orderly shutdown.
- Shutdown records lifecycle state without external infrastructure.
- Restart creates a fresh lifecycle and recovers readiness against the same
  local SQLite path.
- Metrics are emitted as OpenMetrics-compatible text with `_total` counters,
  seconds histograms and bounded label values.
- W3C trace context propagates through HTTP response headers and outbox event
  envelopes.
- Structured logs include correlation fields and redact UPI-like values.
- Performance smoke tests calculate local p50/p95 values without production
  capacity claims.
