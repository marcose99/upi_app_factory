# Generated Application Reliability Objectives

Scope: deterministic local generated application only. These objectives are
operator-readiness benchmarks and do not claim production capacity, regulatory
approval, scheme certification, or live payment readiness.

## SLIs

- Availability SLI: successful local HTTP requests divided by total local HTTP
  requests from `upi_app_factory_http_requests_total`.
- Latency SLI: local request duration from
  `upi_app_factory_http_request_duration_seconds`.
- Dependency SLI: `/ready` success when SQLite integrity and mock dependencies
  report healthy.
- Eventing SLI: transactional outbox envelope creation with W3C `traceparent`
  and bounded synthetic event labels.

## Local SLO Benchmarks

- Readiness: `/ready` returns 200 after startup and 503 during drain.
- Liveness: `/live` remains 200 during drain and becomes unavailable only after
  shutdown.
- Local latency smoke: p95 for 25 in-process health/readiness calls stays under
  50 milliseconds on the validation host.
- Local pagination growth smoke: 30 deterministic SQLite disputes can be listed
  in bounded 10-item pages without duplicate first items across page offsets.
- Local bounded-load smoke: generated tests remain in-process and do not claim
  concurrency, throughput or production capacity.
- Error budget benchmark: at most 1 local request error in 100 deterministic
  smoke probes. This is a test threshold, not a production promise.

## Error Budget Use

If the local benchmark is exhausted, freeze feature changes for the generated
application template until the failing probe, metric, trace or lifecycle test is
repaired. Evidence is kept in validation output and Wave D traceability.
