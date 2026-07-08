# Phase 32 operator portal download center prompt

Integrate the Phase 31 generated application export/download capability into a lightweight local operator portal or portal-ready service layer. The portal layer must call or wrap the existing Phase 31 export function and must never fake generation or export success.

Mandatory inputs:
- `scripts/export_phase31_deep_generated_application_bundle.py`
- `factory/operator_portal/download_center.py`
- `policies/phase32_operator_portal_download_center_policy.json`
- `policies/phase31_deep_generated_application_export_download_policy.json`
- `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase31/operator_download_center_manifest.json`

Download center rules:
- Trigger the governed Phase 31 export locally through the existing export script or function.
- Return bundle metadata, local bundle path, download-ready path, export manifest contents, generation manifest contents, and evidence summary contents.
- Do not report success unless the zip bundle exists and includes `export_manifest.json`, `generation_manifest.json`, and required evidence summaries.
- Do not destructively replace the existing generated workspace.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- No live provider calls.
- No real secrets or credentials.
- No deployment.
- No destructive replacement of the generated workspace.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
