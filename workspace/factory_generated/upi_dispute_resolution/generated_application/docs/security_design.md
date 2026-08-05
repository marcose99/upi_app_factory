# Generated Application Security Design

This generated application is a local mock/simulated UPI dispute-resolution
runtime. It uses security standards as implementation benchmarks only and makes
no certification, regulatory approval, production-readiness, live payment, or
live identity-provider claim.

## API Boundary

- Protected dispute and runtime operations require a signed local bearer token
  by default.
- Header-principal fallback is disabled unless
  `UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL=1` is explicitly set for tests.
- OpenAPI metadata includes a local bearer security scheme plus OAuth2
  authorization-code/PKCE benchmark metadata with `.invalid` identity-provider
  URLs and live provider calls disabled.
- Pydantic request and response boundary models set `extra="forbid"` so unknown
  JSON fields are rejected instead of silently ignored.
- Problem responses use `application/problem+json` and carry correlation IDs.
- Object authorization limits dispute reads to the owning principal unless the
  caller has administrative or read-any authority.
- The versioned failed-debit mutation scopes are separated by intent and role:
  `dispute:evidence:write`, `dispute:investigation:write`,
  `dispute:classify:write`, `dispute:review:write`,
  `dispute:disposition:write`, `dispute:close:write`,
  `dispute:quarantine:write`, `dispute:history:read`, and
  `dispute:audit:read`.
- Case workflow roles are enforced explicitly:
  `customer_support_agent`, `dispute_operations_analyst`,
  `supervisor_approver`, and `audit_reviewer`.
- Human-review approval rejects same-actor self-approval when segregation of
  duties applies, and closure is fail-closed unless disposition and audit
  integrity verification have already succeeded.

## Data Protection

- Raw UPI identifiers are minimized before persistence and API responses expose
  `masked_customer_upi` instead of raw `customer_upi`.
- Logs and generated evidence are designed for synthetic local data and use
  no production secrets; they do not require real credentials.
- External ecosystem adapters remain deterministic mocks with
  no live external integrations; live bank, PSP, NPCI, RBI, payment rail, ODR,
  notification, identity-provider, and OpenAI application calls are disabled.
- Mock adapter resilience checks enforce deterministic payload byte budgets,
  rolling one-minute rate budgets, circuit state, and in-flight pressure before
  local operations. Timeout checks are cooperative elapsed-time checks because
  the generated adapter intentionally avoids worker threads, network calls, and
  third-party runtime dependencies.

## Reliability And Replay Controls

- Create-dispute idempotency keys are bound to a SHA-256 fingerprint of the
  transaction reference, customer UPI, reason, and owner subject. Exact replays
  return the original result; mismatched payload or owner reuse returns a
  conflict.
- Versioned failed-debit commands also require idempotency keys and correlation
  IDs; evidence, investigation, classification, review, disposition,
  quarantine, and closure requests fail closed on stale expected versions.
- SQLite persistence uses migrations with checksum drift detection, explicit
  local-review pragmas, transactional audit/outbox writes, consumer inbox
  replay protection, and optimistic concurrency checks.
- Failed-debit evidence, review decisions, audit-integrity checks, history,
  audit-link hashes, and deterministic simulated-bank snapshots are persisted
  locally in SQLite with no live provider boundary crossings.
- Runtime `/startup`, `/live`, `/ready`, `/health`, and `/metrics` probes are
  documented for the local run pack.

## Control Plane

- The generated policy engine denies merge, push, release, deploy, certify,
  destroy, and silent prompt/model/policy/test self-modification actions.
- Local runtime start requires a scope-bound, unexpired approval nonce.
- Approval nonces are consumed by the policy engine so reuse through the same
  decision boundary is rejected, and the decision returns the consumed nonce as
  a persistence/update contract for surrounding approval stores.
- Portfolio assessment remains recommendation-only.

## Supply Chain Evidence

- Assurance artifacts include ASVS/API/SAMM/threat-model mappings,
  CycloneDX/SPDX-shaped SBOM evidence, dependency inventory, installed
  distribution `RECORD` hash samples, and SLSA-style provenance evidence.
- The evidence proves deterministic source/current-environment reproducibility
  only. Upstream wheel/archive reproducibility remains unattained because no
  repository-owned offline wheelhouse or source archive cache is present and
  dependency installation or network access is prohibited.
