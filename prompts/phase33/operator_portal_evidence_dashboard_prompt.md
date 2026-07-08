# Phase 33 operator portal run/validation evidence dashboard prompt

Add a lightweight local operator portal evidence dashboard service for the generated UPI dispute resolution factory application. The dashboard must help an operator inspect current governed factory state, validation coverage, lifecycle evidence, generated bundle metadata, and safety boundaries.

Mandatory inputs:
- `factory/operator_portal/evidence_dashboard.py`
- `scripts/show_phase33_operator_portal_evidence_dashboard.py`
- `scripts/validate_phase33_operator_portal_evidence_dashboard.py`
- `policies/phase33_operator_portal_evidence_dashboard_policy.json`
- Phase 28, Phase 29, Phase 30, Phase 31, and Phase 32 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/`
- Phase 31 export bundle manifests when locally available

Dashboard rules:
- Expose the current app id and Phase 28 through Phase 33 coverage.
- Show latest relevant tags when available.
- Show Phase 28, Phase 29, Phase 30, Phase 31, and Phase 32 lifecycle artifact availability.
- Show Phase 31 generated export bundle metadata when locally available.
- Show Phase 32 download-center service status.
- Show validator and test command lists.
- Report missing or unknown artifacts as missing or unknown; the dashboard must not fake success.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- No live provider calls.
- No real secrets or credentials.
- No deployment.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
