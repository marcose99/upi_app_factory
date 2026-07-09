# Phase 36 operator portal local web UI prompt

Add a local browser UI for the operator portal that consumes the Phase 35 local API. Keep the UI static or server-rendered, local-first, dependency-minimal, and free of external CDN dependencies.

Mandatory inputs:
- `factory/operator_portal/local_web_api.py`
- `factory/operator_portal/web_ui/`
- `scripts/run_phase36_operator_portal_local_web_ui.py`
- `scripts/validate_phase36_operator_portal_local_web_ui.py`
- `policies/phase36_operator_portal_local_web_ui_policy.json`
- Phase 32 download center service
- Phase 33 evidence dashboard service
- Phase 34 governed validation runner service
- Phase 35 local web API
- Phase 36 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase36/`

UI rules:
- Show local health/status from `GET /health`.
- Show evidence dashboard data from `GET /portal/evidence-dashboard`.
- Show download-center status from `GET /portal/download-center/status`.
- Provide an export action through `POST /portal/download-center/export`.
- Provide validation dry-run through `GET /portal/validation-runner/dry-run`.
- Provide validation run through `POST /portal/validation-runner/run` using structured allowlisted command identifiers only.
- Show latest validation report from `GET /portal/validation-runner/latest-report`.
- Show safety and certification boundaries in the browser.
- Do not expose deployment, merge, tag, or push actions.
- Do not use external CDN assets.
- Do not fake success; show API results truthfully.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- Local-readiness only for the operator portal browser UI.
- No live provider calls.
- No real secrets or credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, broad production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
