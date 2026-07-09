# Phase 41 generated application architecture/code quality upgrade prompt

Upgrade generated application architecture and code quality with deeper maintainability, modularity, and review readiness.

Mandatory inputs:
- `workspace/factory_generated/upi_dispute_resolution/generated_application/`
- `policies/phase41_generated_application_architecture_code_quality_upgrade_policy.json`
- Phase 41 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase41/`
- `scripts/validate_phase41_generated_application_architecture_code_quality_upgrade.py`
- `tests/test_phase41_generated_application_architecture_code_quality_upgrade.py`

Implementation rules:
- Strengthen DDD/layered boundaries, ports/adapters, command/query separation, domain events, repositories/unit-of-work, and error taxonomy.
- Add code quality rules/checklists for generated app maintainability and review readiness.
- Add architecture evidence and a validator that checks the evidence against real generated application files.
- Keep the primary UPI dispute application locally runnable.
- Keep UPI rails, banks, NPCI/RBI interfaces, payment rails, upstream/downstream systems, and third-party services mocked or simulated.
- Do not fake success. Validator failures must fail with actionable errors.
- Do not create real credentials or real secrets.
- Do not enable deployment, merge, tag, or push actions.
- Do not create generated export bundle ZIP files.

Boundary:
- Local-readiness only for generated application architecture and code quality validation.
- No live provider calls.
- No real credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, broad production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
