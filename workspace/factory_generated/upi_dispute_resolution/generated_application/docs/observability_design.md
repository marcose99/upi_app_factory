# Observability Design

The authoritative failed-debit runtime emits deterministic local evidence for
every material transition without relying on external telemetry services.

## Audit chain

- Every dispute command records append-only JSONL audit events with `event_id`,
  `event_type`, `dispute_id`, `actor_role`, `actor_id`, `details`, and
  `created_at_utc`.
- Rejected or prohibited actions are redacted before persistence while keeping
  correlation to the originating command and evidence digest.
- Evidence attachment records retain `content_sha256` and audit-link hashes so
  `/v1/disputes/{dispute_id}/audit-integrity` can verify chain continuity.

## Request and response tracing

- API handlers propagate `x-correlation-id`, `cache-control: no-store`, and
  `x-content-type-options: nosniff` headers on both success and fail-closed
  responses.
- Validation, authorization, and domain exceptions increment structured error
  counters and preserve the dispute path in the problem payload.

## Local metrics

- Runtime counters track dispute creation, idempotent replays, validation
  failures, structured errors, and mock-ecosystem checks.
- Scenario and OpenAPI evidence remain local artifacts under `evidence/` and
  are used by the portal GO gate instead of remote dashboards.

## Operational boundary

- Logs and metrics are intentionally local-first and lightweight; they support
  deterministic review and replay rather than production telemetry claims.
