# Phase 71-82 V63 Remaining Recommendations

Baseline: `5373b9bdd04ccd7760e65345d311362c5bc9a48f`

Campaign: `phase71-82-enterprise-engineering-v63-corrected`

Final report refresh date: 2026-07-27

These recommendations reflect the exact current worktree after the V73 dependency-chain repair. They are not certification, production-readiness, deployment, release, or regulatory-approval claims.

Fresh final-report validation passed for Waves B, D, E and F validators; Phase 42 local run-pack validation; generated application `app/tests` with 39 tests; retained generated compatibility tests with 9 tests; `mypy app factory`; `ruff check app factory tests`; generated application `smoke_test.py`; and Compose syntax validation. Compose validation is configuration-only evidence, not a Docker build/run claim.

## Authoritative Remaining Limitation

1. Add a governed offline wheelhouse or source archive cache only if upstream package artifact reproducibility becomes a required objective. Current evidence records deterministic template bytes, exact local pins, transitive license evidence, installed distribution metadata, and installed-file RECORD hash samples from `canonical_repository_virtualenv`; upstream wheel/archive reproducibility remains unattained.

## Operational Recommendations

1. Continue running the focused Phase 71-82 validators after any future generator, template, validator, or generated-output change: `scripts/validate_phase71_82_wave_b_generated_output.py`, `scripts/validate_phase71_82_wave_d_runtime_observability.py`, `scripts/validate_phase71_82_wave_e_assurance_supply_chain.py`, and `scripts/validate_phase71_82_wave_f_control_plane.py`.
2. Continue running `scripts/validate_phase42_generated_application_local_run_pack.py` after future recipient local-run-pack changes.
3. Continue running generated application pytest targets under the canonical repository virtual environment after future recipient regeneration: `workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests` and `workspace/factory_generated/upi_dispute_resolution/generated_application/tests`.
4. Continue running repository quality gates after future generator/source changes: `mypy app factory` and `ruff check app factory tests`.
5. Keep generated API tests on deterministic ASGI transport patterns where possible. Starlette `TestClient` remains unreliable in this governed environment.
6. Run optional Docker build and full Compose runtime validation only in an environment with package-index access or a pre-warmed governed image/cache. Current evidence includes `docker compose -f compose.yaml config --quiet` only.
7. Keep the standard-library StateGraph-compatible fallback for Phase 13M/13O until `langgraph` is intentionally introduced through governed dependency policy. Do not add it implicitly as a capstone fix.
8. Continue replacing old absolute-path evidence references in historical discovery docs with relative evidence IDs when those docs are revised for publication. Current generated deterministic-build provenance no longer records the user-home virtualenv path.
9. Continue treating older discovery, wave, and benchmark rows as lineage. The current final status is the manifest index plus `IMPLEMENTATION_SUMMARY.md`, `CAPSTONE_ACCEPTANCE.md`, `FINAL_TRACEABILITY_INDEX.json`, `ROADMAP_PHASE71_82_DECISIONS.md`, and this recommendations file.

## Explicit Non-Recommendations

- Do not add live bank, PSP, NPCI, RBI, payment-rail, identity-provider, OpenAI application, signing-service, package-registry, cloud, or deployment integration as part of this campaign.
- Do not add third-party dependencies, package mirrors, wheelhouses, source archive caches, service meshes, Kubernetes infrastructure, telemetry collectors, SaaS tenancy, tenant billing, or production infrastructure unless a later governed campaign explicitly scopes them.
- Do not claim certification, regulatory approval, production readiness, production capacity, formal SBOM certification, attained SLSA level, standards conformance, live payment operation, deployment, release, or real customer-data handling from this evidence.
- Do not remove historical manifests; `generation_manifest_index.json` intentionally retains superseded copies as evidence.
- Do not weaken tests, validators, policy gates, mock-only boundaries, fail-closed approval-token behavior, or generated-output traceability to produce cleaner reports.
