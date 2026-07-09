# Phase 37 end-to-end portal run flow prompt

Add a governed local orchestration flow for the operator portal. The flow must tie together requirement intake availability, generation command status, export/download readiness, validation dry-run, validation run result, and evidence dashboard update state.

Mandatory inputs:
- `factory/operator_portal/end_to_end_run_flow.py`
- `scripts/run_phase37_end_to_end_portal_run_flow.py`
- `scripts/validate_phase37_end_to_end_portal_run_flow.py`
- `policies/phase37_end_to_end_portal_run_flow_policy.json`
- Phase 32 download center service
- Phase 33 evidence dashboard service
- Phase 34 governed validation runner service
- Phase 37 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase37/`

Flow rules:
- Expose explicit stage-level statuses for intake requirements, generation command, export bundle, validation dry-run, validation run, evidence dashboard update, and download availability.
- Clearly distinguish configured, unavailable, missing, passed, failed, and skipped states.
- Do not fake success and do not fake generation success.
- Report generation command configuration or unavailability without treating that as generated application success.
- Use only structured allowlisted validation command identifiers.
- Keep exports local and governed by the existing download center.
- Keep evidence dashboard updates local and read-only.
- Do not expose deployment, merge, tag, or push actions.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- Local-readiness only for the end-to-end operator portal run flow.
- No live provider calls.
- No real secrets or credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, broad production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
