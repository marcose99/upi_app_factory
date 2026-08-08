# Operations Runbook

## Operating posture

- Application ID: `upi_failed_debit_dispute`
- Runtime binding: loopback only (`127.0.0.1`)
- Persistence: local standard-library SQLite
- Runtime LLM calls: `0`
- Real payment/provider calls: `disabled`
- Data posture: fictional-only

## Start and verify

1. Export `REAL_PAYMENT_CALLS=disabled` and keep the default local SQLite path.
2. Run `scripts/run_local.sh`.
3. Verify `GET /health`, `GET /ready`, and `GET /metrics` before operator actions.
4. Confirm `openapi/openapi.json` still advertises the required `/v1/disputes` routes.

## Operator workflow

1. Create a dispute through `POST /v1/disputes` with an idempotency key and correlation header.
2. Attach evidence through `POST /v1/disputes/{dispute_id}/evidence` until the case is investigation-ready.
3. Record investigation and proposed resolution through the governed `/investigation`, `/resolution`, `/timeline`, and `/audit` routes.
4. Preserve application engineering evidence from `evidence/generation_manifest.json`, `evidence/requirements_trace.json`, and the API/OpenAPI outputs for local review.

## Failure handling

- Stop immediately if live-provider settings, real customer data, or non-loopback bindings appear.
- Treat missing readiness, SQLite migration drift, or traceability/evidence mismatches as fail-closed conditions.
- Re-run deterministic local tests before any governed review decision; do not deploy or claim certification.
