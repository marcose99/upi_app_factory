# Implementation Plan

Discovery date: 2026-07-25

## Current Wave Outcome

Wave C implemented confirmed API, identity and external-adapter gaps through the deterministic mock dispute application template and the tracked runnable generated app. Fresh generated output was proved in `/tmp/upi_app_factory_wave_c_generation/phase71_82_wave_c_api_identity_adapters/` with 44 generated files.

Remaining final candidate acceptance is blocked on broader roadmap items outside this Wave C scope and on a pytest/FastAPI-capable validation environment for runtime test execution.

## Implementation Rules

- Implement through factory generator and blueprint paths first.
- Prove fresh generated output after every generator change.
- Keep local-first, deterministic-first, evidence-driven and mock-only behavior.
- Do not add third-party dependencies unless separately justified and approved.
- Do not weaken existing tests.
- Do not make production-readiness, certification, regulatory approval, deployment or live payment claims.

## Step 1: Correct Baseline Ruff Debt

Confirmed gap: `GAP-BASELINE-RUFF-E402`

Generator path:

- `scripts/run_phase13o_local_runnable_operator_packaging.py`

Generated output path:

- `workspace/factory_generated/upi_dispute_resolution/operator_handoff/phase13o_local_runnable_pack/operator_runtime.py`

Lightest implementation:

- Change generated `operator_runtime.py` template so the import of `phase13m_dispute_lifecycle_app.api` is ruff-compliant.
- Prefer a small helper using `importlib.import_module` after `sys.path` setup, or move the import inside a helper with no module-level E402 violation.

Acceptance gates:

- Regenerate phase13o operator pack.
- Ruff generator source and fresh generated operator pack.
- Run phase13o validation script if allowed in the implementation wave.

## Step 2: Promote Transaction and Migration Kernel

Confirmed gaps:

- `GAP-TRANSACTION-SEMANTICS`
- `GAP-MIGRATIONS`
- `GAP-EVENT-DURABILITY`

Blueprint paths:

- `factory/application_engineering/local_platform_kernel.py`
- `factory/application_engineering/deep_composer.py`
- `scripts/run_portal_requirements_driven_application_engineering.py`

Generated output paths:

- `app/*/infrastructure/persistence/migrations/*.sql`
- `app/*/infrastructure/persistence/*unit_of_work*.py`
- `app/*/infrastructure/persistence/*outbox*.py`
- `app/*/domain/*events*.py`

Lightest implementation:

- Wave B implemented this for the deterministic mock dispute app template.
- Commits are outside generated repositories.
- A context-managed SQLite unit of work owns commit/rollback.
- An ordered migration ledger records checksums and detects drift.
- Aggregate state, audit record hash linkage and outbox envelope are persisted in one transaction.
- Outbox replay and inbox duplicate-delivery support use standard library SQLite only.

Acceptance gates:

- Migration ledger and checksum-drift generated tests.
- Rollback generated tests.
- Restart/replay generated tests.
- Outbox replay and duplicate-delivery generated tests.
- Fresh generated manifest and evidence hashes in `workspace/regeneration_runs/phase71_82_wave_b_data_integrity_eventing/generation_manifest.json`.

## Step 3: Generate Standard API Errors and Operability Controls

Confirmed gaps:

- `GAP-API-PROBLEM-DETAILS`
- `GAP-API-OPERABILITY`

Blueprint paths:

- `scripts/run_portal_requirements_driven_application_engineering.py`
- `factory/application_engineering/deep_composer.py`

Generated output paths:

- `app/*/interfaces/api/main.py`
- `app/*/interfaces/api/error_handlers.py`
- `app/*/interfaces/api/schemas.py`
- `openapi/openapi.json`
- `tests/test_api_contract.py`

Wave C implementation:

- Added RFC 9457-compatible `application/problem+json` fields: `type`, `title`, `status`, `detail`, `instance`.
- Added stable problem types, error codes, boundary notice and `correlation_id` extension.
- Added validation detail extension as `invalid_params`.
- Added list pagination limit/cursor contract and hard maximum page size of 100.
- Added OpenAPI 3.1 compatibility metadata, operation IDs, examples and security schemes.

Acceptance gates:

- API error contract tests.
- OpenAPI examples include problem details.
- Pagination/resource limit tests.

## Step 4: Generate Local Identity Boundary

Confirmed gap: `GAP-IAM-BOUNDARY`

Blueprint paths:

- `factory/application_engineering/local_platform_kernel.py`
- `factory/application_engineering/failed_debit_capability.py`
- `scripts/run_portal_requirements_driven_application_engineering.py`

Generated output paths:

- `app/*/security/*`
- `app/*/interfaces/api/main.py`
- `openapi/openapi.json`
- `tests/test_authorization.py`

Wave C implementation:

- Generated a lightweight identity provider and authorization port/profile for deterministic local tests.
- Added local principal headers and route dependencies for function authorization.
- Added object authorization for dispute access and property authorization for protected evidence/domain notes.
- Added OpenAPI local principal security scheme.
- Added RFC 9700-aligned OAuth 2.0/OIDC production-adapter contract metadata with `.invalid` endpoints and no live identity-provider calls.

Acceptance gates:

- Missing/invalid principal tests.
- Role/scope denial tests.
- Object authorization tests.
- No live identity-provider calls.

## Step 5: Generate Lifecycle and Observability Depth

Confirmed gaps:

- `GAP-HEALTH-LIFECYCLE`
- `GAP-METRICS`
- `GAP-RESILIENCE-ADAPTERS`

Blueprint paths:

- `scripts/run_portal_requirements_driven_application_engineering.py`
- `factory/application_engineering/deep_composer.py`
- `factory/operator_portal/runtime_*`

Generated output paths:

- `app/*/interfaces/api/main.py`
- `app/*/observability/*`
- `tests/test_runtime_lifecycle.py`
- `tests/test_observability.py`

Wave C implementation:

- Added explicit timeout, retry budget, jitter, circuit-breaker, rate/resource-limit and degraded-mode contracts for mock adapters.
- Added runtime adapter-contract endpoint guarded by local authorization.
- Preserved mock-only/live-provider fail-closed runtime settings.

Acceptance gates:

- Startup/readiness/liveness/drain tests.
- Metric naming/cardinality/unit tests.
- Trace/log correlation tests.
- Failure-budget and timeout tests for adapters.

## Step 6: Expand Generated Deliverable Tests

Confirmed gap: `GAP-GENERATED-TEST-DEPTH`

Blueprint paths:

- `factory/application_engineering/verification_evidence.py`
- `factory/application_engineering/deep_composer.py`
- `scripts/run_portal_requirements_driven_application_engineering.py`

Generated output paths:

- `tests/`
- `evidence/generated_test_execution.json`
- `evidence/test_catalogue.json`
- `evidence/verification_summary.json`

Wave C implementation:

- Added generated template tests for API/problem details, OpenAPI security metadata, adapter contracts and authorization.
- Added tracked generated-app tests for problem details, OpenAPI 3.1 metadata, pagination max size, function/object/property authorization, and mock-only identity/adapter contracts.
- Added repository Wave C generator propagation test that regenerates fresh output into a temporary workspace and verifies the Wave C generated files are emitted.

Acceptance gates:

- Generated app pytest passes.
- Test inventory maps tests to gaps and requirements.
- Evidence records command, scope, counts and checksums.

## Step 7: Supply-Chain Evidence Without Claims

Confirmed gap: `GAP-SUPPLY-CHAIN`

Blueprint paths:

- `factory/application_engineering/verification_evidence.py`
- `scripts/run_portal_requirements_driven_application_engineering.py`

Generated output paths:

- `evidence/dependency_inventory.json`
- `evidence/cyclonedx_1_7_sbom.json`
- `evidence/spdx_3_0_sbom.json`
- `evidence/slsa_1_2_provenance_shaped.json`
- `evidence/reproducibility_comparison.json`

Lightest implementation:

- Generate dependency inventory from existing manifests and standard library inspection.
- Generate shaped SBOM/provenance evidence with explicit limitations.
- Rebuild/generate twice and compare deterministic artifacts.

Acceptance gates:

- SBOM JSON schema/shape checks.
- Provenance source path and command checks.
- Reproducibility comparison.
- Explicit non-claim fields.

## Final Candidate Gates

Required before any governed review marker:

- Baseline ruff debt fixed at generator and fresh generated-output level.
- Fresh generated application proof exists.
- Targeted ruff on changed Python and generated Python is green.
- Generated application tests are green.
- Evidence manifests are fresh and checksummed.
- Mock-only, no-live-provider, no-real-secret, no-deployment and no-certification-claim boundaries are preserved.
- Source/test/config/dependency changes are reviewed as implementation changes, not discovery artifacts.
