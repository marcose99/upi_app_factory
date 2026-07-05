# Phase 11A.1 Prompt — Essential Agentic Harness Hardening

Add the missing operational controls required before real governed agents
generate application code.

Required controls:

- autonomy levels
- fail-closed tool permission matrix
- human approval ledger schema
- checkpoint and replay policy
- prompt-injection and untrusted-input policy
- secret and environment guard policy
- model/provider/budget policy
- repair-loop limit policy
- generated-code acceptance contract
- agent evaluation rubric
- Phase 11B go/no-go gate

Non-negotiables:

- Agents must not commit, merge, tag, push, or release.
- Agents must not bypass deterministic validators.
- Agents must not access secrets or real customer data.
- Unknown tools and paths must FAIL_CLOSED.
- Human approval is required for protected writes.
- Deterministic validation is required before generated code is accepted.


<!-- PHASE_11A_2_REALISTIC_MOCK_ENGINEERING_GUARDRAILS -->

## Phase 11A.2 Mandatory Realistic Mock Engineering Guardrails

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED,
HIGH_VOLUME_ENGINEERING_REQUIRED, ASYNC_CONCURRENCY_REQUIRED,
LOCAL_FIRST_LIGHTWEIGHT_RUNTIME, PRODUCTION_MIGRATION_READY,
HA_FAILOVER_FAILBACK_DESIGN_REQUIRED,
PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED, STRONG_GUARDRAILS_REQUIRED,
MOCK_BOUNDARY, SYNTHETIC_DATA, HUMAN_APPROVAL_REQUIRED,
DETERMINISTIC_VALIDATION_REQUIRED, FAIL_CLOSED

### Realistic but strictly mock

All generated application and ecosystem components must behave like realistic
enterprise payment-dispute software, but every external dependency remains a
mock adapter, simulator, fixture, or synthetic service. Do not add live bank,
NPCI, RBI, PSP, ledger, notification, ODR, merchant, customer, or account-system
integrations.

### High-volume engineering

Design request, event, batch, and replay paths to handle high data volume in a
local-first way. Use bounded queues, pagination, streaming-style processing,
chunking, idempotency keys, backpressure, rate limits, retries, timeouts, and
resource limits where applicable.

### Async, concurrency, and parallelism

Use async I/O, worker pools, task queues, concurrency limits, and parallel
validation where realistic. Avoid unbounded concurrency. Document why each
parallel path is safe, deterministic, idempotent, and locally runnable.

### Availability, failover, and failback

Architecture and design outputs must include high availability, failover,
failback, retry, circuit-breaker, degraded-mode, checkpoint, replay, and recovery
considerations. Locally, these may be simulated with lightweight mock services
and deterministic fault-injection tests.

### Production-quality observability

Add structured logs, metrics, traces, health checks, readiness checks, liveness
checks, audit events, correlation IDs, run IDs, decision IDs, retry counters,
queue-depth metrics, latency histograms, and error taxonomies where applicable.
Keep the implementation lightweight locally, but design adapters for later
migration to production observability systems.

### Local-first, migration-ready

Default runtime must use lightweight local tools. Every mock or local component
must have a clear migration seam so it can later be replaced one by one with
production infrastructure without changing business logic.

### Strong guardrails

Generated work must preserve mock boundaries, synthetic data labels, human
approval gates, deterministic validation, fail-closed behavior, secret blocking,
prompt-injection resistance, budget controls, and repair-loop limits.
