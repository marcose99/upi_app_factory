# Phase 71-82 V63 Final Repair Report

## Scope

Independent review findings repaired in this pass:

- `CRIT-GENERATED-PROPAGATION-INCOMPLETE`
- `HIGH-AUTHORITATIVE-MATRIX-STALE`
- `HIGH-TEST-GATE-INCOMPLETE`
- `HIGH-FRESH-FINAL-MANIFEST-NOT-PERSISTED`
- `HIGH-RESILIENCE-ADAPTERS-PARTIAL`
- `HIGH-GENERATED-OUTPUT-PROPAGATION`
- `HIGH-IAM-OIDC-DEPTH`
- `HIGH-SUPPLY-CHAIN-COMPONENT-IDENTITY`
- `MED-LIST-ENDPOINT-STUB`
- `MEDIUM-ASVS-EVIDENCE-SHALLOW`
- `HIGH-OPENAPI-SECURITY-CONTRACT-INCOMPLETE`
- `HIGH-API-AUTH-001`
- `HIGH-API-OPS-001`
- `HIGH-PII-001`
- `HIGH-GENERATED-TESTS-001`
- `MED-IAM-001`
- `MED-PERFORMANCE-EVIDENCE-SHALLOW`
- `MED-RUNTIME-CONFIGURATION-LIMITED`
- `HIGH-001-recipient-entrypoint-still-runs-legacy-app`
- `HIGH-002-capstone-fresh-generation-evidence-does-not-match-current-template`
- `HIGH-001-default-runnable-generated-application-bypasses-api-identity`
- `MEDIUM-001-capstone-acceptance-document-stale`
- `MEDIUM-002-declared-negative-test-obligation-has-no-generated-negative-test-file`
- `MEDIUM-001-generated-app-cleartext-upi-persistence`
- `MEDIUM-002-spdx-exact-component-identity-parity`
- `HIGH-IDEMPOTENCY-PAYLOAD-NOT-BOUND`
- `HIGH-RECIPIENT-HEALTH-CHECK-STATUS-DRIFT`
- `HIGH-EVIDENCE-INTEGRITY-001`
- `MED-ASVS-API-001`
- `MED-APPROVAL-REPLAY-001`
- `MED-DOC-SECURITY-001`
- `MED-SQLITE-LOCAL-CONCURRENCY`
- `HIGH-CREATE-DISPUTE-IDEMPOTENCY-NOT-ATOMIC`
- `HIGH-APPROVAL-RUNTIME-EXPIRY-DIGEST-GAP`
- `MED-PRIMARY-FASTAPI-BEHAVIORAL-ENDPOINT-TESTS`
- `MED-DUPLICATE-BUSINESS-SUBMISSION-PROTECTION`
- `MED-PERFORMANCE-EVIDENCE-SMOKE-ONLY`
- `MED-EVIDENCE-INTEGRITY-STALE-GENERATION-MANIFESTS`
- `MED-DOCS-STALE-MERGE-PUSH-STATEMENT`
- `MEDIUM-RECIPIENT-DOC-TEST-PATH`
- `MEDIUM-FASTAPI-LIFECYCLE-DEPRECATION`
- `MEDIUM-APPROVAL-DEFAULT-TOKEN`
- `MEDIUM-PROVENANCE-ABSOLUTE-HOST-PATH`
- `HIGH-LEGACY-COMPATIBILITY-SURFACE-BYPASSES-HARDENED-API`
- `MEDIUM-RESILIENCE-ADAPTER-PRIMITIVE-IS-CONTRACTUAL-NOT-ENFORCING`
- `MEDIUM-TRACKED-REPORT-OVERSTATES-LEGACY-DELEGATION`
- `MED-DOC-REMAINING-RECOMMENDATIONS-STALE-LIFESPAN`
- `AUTH-MYPY-V73-COMPAT-FACADE-ANY-RETURN`

## Repairs

- Propagated the final generator output into `workspace/factory_generated/upi_dispute_resolution/generated_application`.
- Persisted the final pre-review 66-file manifest at `workspace/regeneration_runs/phase71_82_v63_final_propagation/generation_manifest.json`.
- Persisted the independent-review repair 78-file manifest at `workspace/regeneration_runs/phase71_82_v63_independent_review_repair/generation_manifest.json`.
- Added a recipient manifest copy at `workspace/factory_generated/upi_dispute_resolution/generated_application/generation_manifest.phase71_82_v63_final_propagation.json`.
- Replaced the stale legacy `upi_dispute_app.main` implementation with a compatibility facade that always delegates to the regenerated hardened API, including when legacy `repository`, `audit_logger`, or `settings` keyword arguments are supplied.
- Updated recipient README, local start script, smoke test and health check to target `generated_application.app.interfaces.api.main:app`, `/startup`, `/live`, `/ready` and `/metrics`.
- Added RFC 9457-compatible handlers for domain, HTTP and request-validation failures.
- Added deterministic signed local bearer-token issuance and verification with local issuer, audience, expiry, role and scope claims.
- Added persisted `owner_subject`, object-level `GET /disputes/{dispute_id}` authorization and route-level scope checks.
- Replaced `GET /disputes` empty stub behavior with persisted SQLite listing, bounded `limit`, `cursor`, `next_cursor` and explicit 429 problem-details behavior for oversize pages.
- Added security headers in API middleware.
- Added deterministic adapter retry, timeout, circuit-breaker reset, backpressure and degraded-response behavior with generated tests.
- Replaced SPDX `NOASSERTION` package licenses with deterministic local SPDX identifiers and component identity references.
- Attached OpenAPI security requirements, operation IDs and local-boundary metadata to every protected dispute and runtime operation.
- Required signed local bearer principals with `runtime:drain` or `runtime:diagnostics` scope for `/drain` and `/runtime/diagnostics`.
- Kept signed local bearer-token auth as the default; `X-Local-*` header principals now require explicit `UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL=1` test profile.
- Replaced raw dispute response `customer_upi` with `masked_customer_upi` and sanitized validation problem details so submitted input values are not serialized.
- Replaced newly persisted raw UPI values with a salted digest and masked local display value in SQLite.
- Made SQLite state path explicit through `UPI_DISPUTE_SQLITE_PATH`, defaulting to `state/local_disputes.sqlite3`, and documented one-process-per-state-file isolation.
- Added generated performance smoke coverage for bounded SQLite pagination growth.
- Updated persisted legacy generated API tests to call the regenerated authenticated API contract through the compatibility facade.
- Added offline lock evidence from `requirements/ci-lock.txt`, exact runtime pins, and transitive dependency license evidence while preserving no-network/no-new-dependency behavior.
- Aligned SPDX package versions and purls to CycloneDX exact resolved versions and added installed distribution RECORD hash evidence from the canonical virtual environment.
- Added generated negative tests under `generated_application/app/tests/negative/`.
- Added review-repair propagation manifest at `workspace/regeneration_runs/phase71_82_v63_review_repair_propagation/generation_manifest.json` and copied it to the recipient generated application.
- Added payload-bound idempotency fingerprints with exact replay only and conflict on key reuse with mismatched transaction, customer UPI, reason, or owner subject.
- Aligned `health_check.py` with the generated runtime probe statuses `started`, `live`, and `ready`.
- Added strict generated API boundary models with `extra="forbid"` and generated tests for unknown-field rejection.
- Added stateful generated control-plane nonce consumption with a returned consumed-nonce contract and replay tests.
- Added SQLite busy timeout, WAL journal mode where available, and per-database migration caching after startup.
- Regenerated and propagated current 78-file output with `generated_application/docs/security_design.md` included in the template manifest.
- Added recipient manifest copy at `workspace/factory_generated/upi_dispute_resolution/generated_application/generation_manifest.phase71_82_v63_payload_bound_health_security_repair.json`.
- Added atomic idempotency reservation/finalization before dispute/audit/outbox creation and explicit conflict handling for mismatched idempotency-key reuse.
- Added generated duplicate business-submission protection using a unique transaction/customer/reason fingerprint.
- Added generated primary FastAPI behavioral tests for create, replay, idempotency conflict, missing/invalid bearer token, object authorization, list pagination, validation problem details and middleware headers.
- Replaced synthetic generated performance percentile evidence with actual local service create/list timing smoke evidence without production capacity claims.
- Added expiring operator runtime approvals with digest re-verification at consumption plus replay, expiry, tamper and wrong-scope tests.
- Added a current generated manifest index and marked historical recipient manifest copies as superseded evidence.
- Scoped the README merge/push statement to its historical baseline and recorded the current controller-owned uncommitted repair posture.
- Regenerated and propagated current 78-file output with `phase71_82_v63_atomic_runtime_api_repair`.
- Corrected `docs/deployment/GENERATED_APPLICATION_LOCAL_DEPLOYMENT_GUIDE.md` so recipient-root test execution uses `PYTHONPATH=.. python -m pytest -q app/tests`.
- Replaced generated FastAPI startup/shutdown `@app.on_event` hooks with an application lifespan context in the template and propagated recipient output.
- Added generator validation that rejects regenerated API templates containing `@app.on_event` lifecycle hooks.
- Removed source-known runtime and portfolio approval-token fallback acceptance; approval token environment variables now fail closed when absent, with deterministic values installed only by pytest fixtures.
- Replaced generated deterministic-build provenance user-home virtualenv path with `canonical_repository_virtualenv installed dist-info RECORD metadata`.
- Added supply-chain validation rejecting user-home absolute paths in generated deterministic build provenance.
- Regenerated and propagated the V73 78-file output with `phase71_82_v73_independent_review_repair`, persisted its recipient manifest copy, and updated the recipient manifest index to make it the then-current authoritative candidate.
- Quarantined the recipient legacy dependency-injection FastAPI runtime surface behind explicit injected `repository` and `audit_logger` arguments without a `database_path`; the default legacy import facade and all `database_path` uses still delegate to the hardened API with signed bearer-token identity, RFC 9457 problem details, OpenAPI 3.1 metadata, security headers, lifecycle probes, and OpenMetrics text output.
- Strengthened the generated deterministic adapter primitive with payload byte-budget checks, rolling one-minute rate-budget checks, and in-flight increment/decrement around each operation attempt. Timeout evidence remains a cooperative elapsed-time check because the generated adapter intentionally avoids worker threads, network calls, and third-party dependencies.
- Updated the stale remaining-recommendations lifespan item to record that generated FastAPI lifecycle handling now uses `lifespan`.
- Regenerated and propagated the current V73 78-file surface with `phase71_82_v73_review_rerun_2_repair`, copied the recipient manifest to `workspace/factory_generated/upi_dispute_resolution/generated_application/generation_manifest.phase71_82_v73_review_rerun_2_repair.json`, and updated the recipient manifest index to mark it current while retaining prior manifests as historical evidence.
- Diagnosed the V73 authoritative mypy failure as a template-side type dependency chain in `generated_application/app/upi_dispute_app/main.py`: the quarantined legacy-injection harness imports compatibility modules that are not part of the current 78-file template surface, so `payload_fingerprint` is dynamically resolved during `mypy app factory` and its result was treated as `Any` inside a helper declared to return `str`.
- Narrowed that legacy-only fingerprint return value to `str` in the governed template, preserving the default hardened API delegation path and the explicit legacy-injection quarantine.
- Regenerated and propagated the current V73 78-file surface with `phase71_82_v73_review_rerun_3_dependency_chain_repair`, copied the recipient manifest to `workspace/factory_generated/upi_dispute_resolution/generated_application/generation_manifest.phase71_82_v73_review_rerun_3_dependency_chain_repair.json`, and updated the recipient manifest index to mark it current while retaining prior manifests as historical evidence.
- Proved the V73 dependency-chain repair preserved the exact previous 78 generated manifest paths and direct template/recipient byte equality over all 78 entries.

## Remaining Authoritative Blockers

- Repository and generated `pytest` execution require the canonical virtual environment at `<canonical-venv>`; `/usr/bin/python` remains blocked because it lacks pytest, FastAPI, Pydantic, Uvicorn and HTTPX.
- Upstream wheel/archive hash capture remains blocked because no offline wheelhouse or source archive cache is checked in, registry/network access is prohibited, and dependencies were not added. Exact pins, transitive license evidence, and installed distribution RECORD hashes are now recorded from local artifacts.
- Upstream artifact reproducibility remains unattained; source/current-environment reproducibility is limited to deterministic template bytes, exact local pins, installed distribution metadata and RECORD hash evidence.
- Starlette `TestClient` is unreliable for the generated app in this governed environment; generated API contract tests now use explicit local `httpx.ASGITransport`, matching the repository's deterministic ASGI test-client pattern without network calls.

No live bank, PSP, NPCI, RBI, payment rail, identity-provider or OpenAI application calls were introduced. No deployment, release, certification, production-readiness or regulatory-approval claim is made.
