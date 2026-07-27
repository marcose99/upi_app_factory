# Phase 71-82 V63 Decisions

Discovery date: 2026-07-25

Final report refresh date: 2026-07-27

Baseline: `5373b9bdd04ccd7760e65345d311362c5bc9a48f`

Campaign: `phase71-82-enterprise-engineering-v63-corrected`

## Decision Boundary

This roadmap records the decisions as they stand in the exact current worktree. It separates implemented local deterministic engineering work from remaining limitations and non-claims.

No item below is a production-readiness, certification, regulatory approval, deployment, release, live-integration, production-capacity, or Git-operation claim.

## D1 Final Acceptance Is Local Deterministic Evidence Only

Decision: accept the current campaign only as deterministic local-first generated-output propagation with benchmark-oriented evidence.

Current state:

- The current authoritative generated manifest is `workspace/factory_generated/upi_dispute_resolution/generated_application/generation_manifest.phase71_82_v73_review_rerun_3_dependency_chain_repair.json`.
- The generated manifest index records 78 current generated files and retains prior manifests as superseded evidence.
- The final report set is the current acceptance surface; older wave/discovery rows may preserve historical pre-repair language.

Limit: this is not certification, production readiness, deployment readiness, regulatory approval, production capacity, live payment capability, or upstream artifact reproducibility.

## D2 Repairs Must Stay Generator-Sourced

Decision: repair quality debt through generator/template/source changes and fresh generated output, not through test weakening or third-party dependency additions.

Current state:

- Phase 13M/13O use a real `langgraph` integration when present and a bounded standard-library StateGraph-compatible fallback otherwise.
- V73 dependency-chain repair addressed the authoritative `mypy app factory` failure in the compatibility facade while preserving the hardened API delegation path.
- Fresh report-refresh validation passed for Waves B, D, E and F validators, Phase 42 local run-pack validation, generated application `app/tests` with 39 tests, retained generated compatibility tests with 9 tests, `mypy app factory`, `ruff check app factory tests`, generated application `smoke_test.py`, Compose configuration validation, and template/recipient equality proof.

Limit: the system `/usr/bin/python` remains unsuitable for pytest/FastAPI/Pydantic/Uvicorn/HTTPX validation; canonical virtualenv validation is the recorded executable path.

## D3 Generated Application Depth Is The Acceptance Target

Decision: the hardened generated application, not the legacy compatibility app, is the candidate depth surface.

Current state:

- The generated app includes transaction boundary, migration ledger, audit log, outbox/inbox, optimistic concurrency, payload-bound idempotency, duplicate business-submission rejection, strict API schemas, RFC 9457-style problem details, OpenAPI security contracts, runtime lifecycle controls, metrics, tracing, safe logs, generated tests, local run-pack scripts, and assurance evidence.
- The legacy `upi_dispute_app.main` route remains only as compatibility facade/quarantined injected harness.

Limit: runtime remains local/mock-only and SQLite-first. It is not a production deployment architecture, live payment integration, or real customer-data system.

## D4 Identity Boundary Is Local And Deterministic

Decision: identity and authorization are implemented as local signed bearer-token contracts and local test fixtures, not live IAM.

Current state:

- Generated API routes require signed local bearer principals by default.
- Header-principal fallback requires explicit `UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL=1` test profile.
- Runtime and portfolio approval-token fallbacks fail closed when approval-token environment variables are absent.

Limit: no live OAuth/OIDC provider, identity-provider, bank IAM, customer identity verification, or production secrets service was integrated.

## D5 Events And Persistence Are Local Engineering Controls

Decision: use durable local SQLite/outbox/inbox semantics where they add deterministic engineering value.

Current state:

- Domain events, transactional outbox, inbox duplicate guard, retry handling, audit linkage, migration drift checks, restart tests, optimistic concurrency, idempotency conflict handling, and AsyncAPI evidence are present in generated output.

Limit: no live broker, PSP event rail, NPCI integration, distributed production consistency claim, or production database architecture is claimed.

## D6 Observability Stays Dependency-Light

Decision: satisfy local benchmark evidence with standard-library/local-compatible observability instead of introducing collectors or heavyweight infrastructure.

Current state:

- Generated output includes JSON logs with redaction, W3C trace context propagation, OpenMetrics-compatible text exposition, lifecycle probes, runtime diagnostics, local smoke timing evidence, and tests.

Limit: no Prometheus server, OpenTelemetry collector, service mesh, cloud telemetry backend, live monitoring integration, or production-capacity claim is included.

## D7 Supply-Chain Evidence Is Benchmark-Oriented And Non-Claiming

Decision: generate structured local evidence and clearly state unresolved artifact reproducibility boundaries.

Current state:

- Generated evidence includes CycloneDX/SPDX-shaped SBOMs, dependency/license inventory, deterministic build manifest, provenance-style verification, OpenSSF-oriented assessment, and standards benchmark mapping.
- Exact local pins, transitive license evidence, installed distribution metadata, and RECORD hash evidence are recorded from `canonical_repository_virtualenv`.

Limit: upstream wheel/archive reproducibility is unattained until a governed offline wheelhouse or source archive cache exists. No formal SBOM certification or attained SLSA level is claimed.

## D8 Historical Evidence Must Be Retained

Decision: retain prior manifests and historical reports as evidence instead of deleting or rewriting history.

Current state:

- `generation_manifest_index.json` marks current and superseded manifests explicitly.
- Historical rows with earlier file counts and blockers remain useful as lineage but are not the current final acceptance statement.

Limit: consumers must read the final reports and manifest index for current status rather than treating every historical discovery row as current truth.

## Phase 71-82 Outcome

Phase 71: benchmark/control catalog and discovery artifacts established.

Phase 72: generator-sourced operator/runtime quality debt repaired without adding dependencies.

Phase 73: migration ledger, transaction boundary, audit, outbox/inbox, idempotency, duplicate-submission handling, and concurrency controls promoted into generated output.

Phase 74: RFC 9457-style problem details, OpenAPI 3.1 metadata, strict API contracts, and API operability controls generated.

Phase 75: local signed-token identity and authorization contracts generated and tested.

Phase 76: lifecycle probes, graceful drain/shutdown, restart evidence, and local runtime packaging generated.

Phase 77: dependency-light metrics, trace context, and PII-safe log evidence generated.

Phase 78: generated app tests expanded across unit, contract, integration, negative, resilience, security, replay, performance smoke, audit, and compatibility targets.

Phase 79: SBOM/provenance/reproducibility evidence generated with explicit non-claims and an upstream artifact reproducibility blocker.

Phase 80: fresh generated output proven and propagated, with 78-file authoritative V73 manifest evidence.

Phase 81: targeted gates recorded for validators, pytest targets, ruff, mypy, smoke scripts, and Compose configuration.

Phase 82: governed final report package prepared as local deterministic evidence only, with no certification, release, deployment, production-readiness, live-integration, or Git-operation claim.
