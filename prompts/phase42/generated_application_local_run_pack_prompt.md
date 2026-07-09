# Phase 42 generated application local run pack prompt

Create a local run pack for the generated UPI dispute application so a reviewer
can run and validate it locally with minimal confusion.

Mandatory inputs:
- `workspace/factory_generated/upi_dispute_resolution/generated_application/`
- `policies/phase42_generated_application_local_run_pack_policy.json`
- Phase 42 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase42/`
- `scripts/validate_phase42_generated_application_local_run_pack.py`
- `tests/test_phase42_generated_application_local_run_pack.py`

Implementation rules:
- Add generated app local run documentation, `.env.example` defaults, startup
  script, validation script, reset/clean script, local smoke test, and health
  checks.
- Keep the run pack local Python based. Do not add Docker Compose unless it is
  lightweight, safe, and cannot be confused with a release path.
- Keep UPI rails, banks, NPCI/RBI interfaces, payment rails, upstream/downstream
  systems, and third-party services mocked or simulated.
- Validate real generated application files and in-process smoke behavior.
- Do not fake success. Validator failures must fail with actionable errors.
- Do not create real credentials or real secrets.
- Do not enable deployment, merge, tag, or push actions.
- Do not create generated export bundle ZIP files.

Boundary:
- Local-readiness only for generated application local review.
- No live provider calls.
- No real credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI
  approval, bank approval, broad production readiness, live payment capability,
  or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
