# Phase 38 portal UX polish and operator guides prompt

Polish the local operator portal user experience and create practical operator guides for running the factory safely from a local checkout.

Mandatory inputs:
- `factory/operator_portal/local_web_api.py`
- `factory/operator_portal/web_ui/static/index.html`
- `factory/operator_portal/web_ui/static/app.js`
- `factory/operator_portal/web_ui/static/styles.css`
- `factory/operator_portal/operator_guides.py`
- `docs/phase38/`
- `policies/phase38_portal_ux_polish_and_operator_guides_policy.json`
- Phase 38 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase38/`

Implementation rules:
- Add local operator, troubleshooting, portal workflow, and status taxonomy guides.
- Expose operator-facing explanations for statuses, boundaries, expected outputs, and safe next steps.
- Improve API and UI errors with actionable local messages.
- Keep validation commands allowlisted; never execute arbitrary shell text.
- Do not fake success.
- Do not create real credentials.
- Do not enable deployment, merge, tag, or push actions.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- Local-readiness only for operator guides and portal workflows.
- No live provider calls.
- No real credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, broad production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
