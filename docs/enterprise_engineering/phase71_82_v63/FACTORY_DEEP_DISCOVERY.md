# Factory Deep Discovery

Discovery date: 2026-07-25

Scope: read-only inspection of the exact governed worktree at `/home/marcose/projects/.upi_app_factory_campaigns/20260725T143850Z-975913`.

Baseline: `5373b9bdd04ccd7760e65345d311362c5bc9a48f`

Campaign: `phase71-82-enterprise-engineering-v63-corrected`

## Boundaries

This artifact is discovery evidence only. It does not claim production readiness, certification, regulatory approval, deployment, or live payment capability.

Authoritative benchmark statements are separated from engineering opinions and recommendations in the matrix and roadmap artifacts for this phase.

## Repository Shape

The repository is a local-first governed factory with:

- Factory source under `factory/`, `scripts/`, `app/`, `adapters/`, `config/`, `policies/`, `factory_governance/`, and `prompts/`.
- Generated and lifecycle evidence under `workspace/factory_generated/upi_dispute_resolution/` and `workspace/deep_engineering_campaign/`.
- Extensive repository tests under `tests/`.
- Existing phase71-82 v63 benchmark seed artifacts under `docs/enterprise_engineering/phase71_82_v63/` and `governance/benchmarks/phase71_82_v63/`.

## Generator Surfaces

Confirmed factory generation paths:

- `factory/generators/mock_dispute_app_generator.py`
  - Deterministic template generator.
  - Copies `factory/templates/mock_dispute_app/*`.
  - Validates phase2, phase3, phase28 and phase29 governance inputs.
  - Emits manifest fields that preserve mock-only, no-live-provider, no-real-secret, no-deployment and no-certification-claim boundaries.

- `factory/templates/mock_dispute_app/`
  - Template root used by the older deterministic generator.
  - Manifest: `factory/templates/mock_dispute_app/template_manifest.v1.json`.

- `factory/application_engineering/deep_composer.py`
  - Deep local profile composer for `upi_failed_debit_dispute`.
  - Generates domain, application, API, SQLite migration, docs, OpenAPI stub and evidence.
  - Enforces `local_only=True`, `mock_only=True`, `llm_runtime_calls=0`, and `real_payment_calls="disabled"`.
  - Contains a generated `outbox_events` table in the initial SQL but not a full dispatcher/replay contract in the generated application code.

- `factory/application_engineering/failed_debit_capability.py`
  - Richer domain capability module.
  - Uses typed domain value objects, policies, local authorization port, and state transitions.
  - Provides stronger domain primitives than the compatibility generated app.

- `factory/application_engineering/local_platform_kernel.py`
  - Contains a local platform kernel with migration ledger, outbox message table and authorization port.
  - This is important partial coverage, but it is not fully propagated into all generated application outputs inspected.

- `scripts/run_portal_requirements_driven_application_engineering.py`
  - Operator portal adapter and compatibility/deep profile command boundary.
  - Enforces app id validation, output/evidence roots under workspace, approval token, mock safety, local evidence, and generated tests.
  - Uses subprocess for local pytest execution inside generated application evidence.
  - Contains generated compatibility application source templates inside `_project_files`.

- `factory/operator_portal/deep_portal_integration.py`
  - Integrates requirements compile/proposal/approved run/download flows.
  - Exposes source/evidence inventories and safe archive creation for portal publications.

- `scripts/run_phase13o_local_runnable_operator_packaging.py`
  - Generates the phase13o local runnable operator pack.
  - Confirmed source of the controller-supplied ruff E402 debt in generated `operator_runtime.py`.

## Governance and Policy Inputs

Confirmed governance inputs relevant to generated application depth:

- `factory_governance/phase2/upi_dispute_requirements.v1.json`
- `factory_governance/phase2/mock_external_system_contracts.v1.json`
- `factory_governance/phase3/architecture_design_contract.v1.json`
- `factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json`
- `policies/phase28_generated_application_architecture_depth_policy.json`
- `policies/phase29_generated_application_deep_structure_policy.json`
- `policies/phase30_deep_generated_application_regeneration_policy.json`
- `policies/phase31_deep_generated_application_export_download_policy.json`

These inputs preserve the local/mock/non-claim boundary. They do not by themselves prove production-oriented generated output coverage for every benchmark control.

## Existing V63 Material

Existing files found before this discovery:

- `docs/enterprise_engineering/phase71_82_v63/AUTHORITATIVE_BENCHMARK_AND_ROADMAP_V61.md`
- `docs/enterprise_engineering/phase71_82_v63/ENGINEERING_OPINIONS.md`
- `docs/enterprise_engineering/phase71_82_v63/RECOMMENDATIONS_AND_ROADMAP.md`
- `docs/enterprise_engineering/phase71_82_v63/RETENTION_POLICY.md`
- `governance/benchmarks/phase71_82_v63/enterprise_engineering_benchmark_v61.json`

The existing benchmark seed already separates source catalog, controls, opinions and recommendations conceptually, but the requested v63 discovery artifacts were not present before this work.

## Baseline Ruff Debt Verification

Controller-supplied evidence path was readable:

`/home/marcose/.local/state/upi_app_factory/phase71-82-enterprise-engineering-v63-recovery-multicycle/20260725T164240Z-1208028/campaign-state/20260725T164241Z-recovery-1208028/logs/baseline_changed_python_ruff_02.log`

The log shows ruff checking a long generated-output scope and reporting one violation:

- `E402 Module level import not at top of file`
- Reported file: `workspace/factory_generated/upi_dispute_resolution/operator_handoff/phase13o_local_runnable_pack/operator_runtime.py`
- Reported line: import of `phase13m_dispute_lifecycle_app.api` after runtime `sys.path.insert`.

The generated output file was not present in the current worktree at that path during discovery, but the generating source was found and verified:

- `scripts/run_phase13o_local_runnable_operator_packaging.py`
- It renders `operator_runtime.py` with `PROJECT_ROOT`, `PHASE13M_APP_DIR`, conditional `sys.path.insert`, and then imports `create_case` and `progress_case_to_resolution`.

Status: CONFIRMED as generator-sourced baseline debt.

Acceptance implication: because this task forbids source/generated-output modifications, the E402 remediation cannot be completed in this discovery-only wave. It must be fixed in the generator and proven by a fresh generated operator pack before final-candidate acceptance.

## Factory Strengths

- Local-first and mock-only controls are explicit and repeated across generator manifests, settings and documentation.
- Output/evidence root resolution uses `Path` and workspace containment checks.
- Approval token and protected-action posture are explicit for operator-triggered generation.
- Deep composer and verification evidence modules already model many desired generated-app evidence artifacts.
- The local platform kernel has partial primitives for migration ledger, outbox and authorization.
- Portal integration supports source/evidence inventories and deterministic archives.
- Repository tests are broad and phase-oriented.

## Factory Gaps

Confirmed or partial factory gaps are mapped in `STANDARDS_GAP_MATRIX.json`. The highest-impact factory-side findings are:

- Baseline generated operator pack ruff E402 is generator-sourced and must be corrected in `scripts/run_phase13o_local_runnable_operator_packaging.py`.
- Deep capability primitives are not uniformly propagated into all generated applications and portal publications.
- Generated compatibility application templates in `scripts/run_portal_requirements_driven_application_engineering.py` use lower-bound dependencies and compatibility-oriented app depth.
- The factory has evidence generators for ASVS, SSDF, CycloneDX-shaped and SLSA-shaped artifacts, but inspected outputs should not be treated as conformance or certification claims.
- Existing generated application depth is uneven across compatibility scaffold, phase31 export remnants, portal publications and deep engineering campaign output.

## Authoritative Discovery Conclusion

The factory has a strong governed deterministic foundation, but final candidate acceptance for phase71-82 v63 cannot be reached from discovery artifacts alone. At minimum, source changes are required to fix the generator-sourced ruff debt and to propagate production-oriented blueprint improvements through fresh generated outputs, tests and evidence.
