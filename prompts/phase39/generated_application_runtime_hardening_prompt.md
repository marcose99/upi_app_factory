# Phase 39 generated application runtime hardening prompt

Harden the primary generated UPI dispute application runtime so it behaves closer to a real local production-disciplined app while remaining local, safe, and mock-only.

Mandatory inputs:
- `workspace/factory_generated/upi_dispute_resolution/generated_application/`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/.env.example`
- `policies/phase39_generated_application_runtime_hardening_policy.json`
- Phase 39 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase39/`
- `scripts/validate_phase39_generated_application_runtime_hardening.py`
- `tests/test_phase39_generated_application_runtime_hardening.py`

Implementation rules:
- Add typed local runtime settings and a `.env.example` with placeholders only.
- Add startup checks that fail closed when live provider calls, real secrets, or non-mock ecosystem mode are requested.
- Improve structured error handling, input validation, idempotency, persistence boundaries, structured logging, and local observability hooks.
- Keep external UPI, bank, NPCI, RBI, payment rail, upstream, downstream, and third-party integrations mocked or simulated.
- Do not fake success.
- Do not create real credentials or real secrets.
- Do not enable deployment, merge, tag, or push actions.

Boundary:
- Local-readiness only for the generated application runtime.
- No live provider calls.
- No real credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, broad production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
