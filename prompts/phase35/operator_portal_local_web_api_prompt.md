# Phase 35 operator portal local web API prompt

Add a local-only FastAPI backend for the operator portal. The API must expose existing governed services through safe endpoints without deployment, real secrets, live providers, or uncontrolled command execution.

Mandatory inputs:
- `factory/operator_portal/local_web_api.py`
- `scripts/run_phase35_operator_portal_local_web_api.py`
- `scripts/validate_phase35_operator_portal_local_web_api.py`
- `policies/phase35_operator_portal_local_web_api_policy.json`
- Phase 32 download center service
- Phase 33 evidence dashboard service
- Phase 34 governed validation runner service
- Phase 35 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase35/`

Endpoint rules:
- Provide `GET /health`.
- Provide `GET /portal/evidence-dashboard`.
- Provide `GET /portal/download-center/status`.
- Provide `POST /portal/download-center/export`.
- Provide `GET /portal/validation-runner/dry-run`.
- Provide `POST /portal/validation-runner/run`.
- Provide `GET /portal/validation-runner/latest-report`.
- Use local TestClient coverage rather than a deployed server.
- The validation runner endpoint must accept only structured allowlisted command identifiers and must never execute arbitrary command strings.
- The API must not expose deployment, merge, tag, or push actions.
- The API must preserve the `certification_ready_not_certified` posture and must not fake success.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- Local-readiness only for the operator portal API.
- No live provider calls.
- No real secrets or credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
