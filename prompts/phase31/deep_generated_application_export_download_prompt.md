# Phase 31 deep generated application export/download prompt

Create a governed local export/download bundle for the deep regenerated UPI dispute resolution generated application. Use the Phase 29 deterministic generator and package the generated application plus evidence so an operator or recipient can inspect the result without replacing the existing generated workspace.

Mandatory inputs:
- `factory/generators/mock_dispute_app_generator.py`
- `factory/templates/mock_dispute_app/template_manifest.v1.json`
- `policies/phase31_deep_generated_application_export_download_policy.json`
- `policies/phase30_deep_generated_application_regeneration_policy.json`
- `policies/phase29_generated_application_deep_structure_policy.json`
- `factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json`
- `prompts/phase28/generated_application_architecture_depth_prompt.md`

Export rules:
- Run the Phase 29 deterministic generator into a controlled Phase 31 export workspace.
- Do not destructively replace the existing generated workspace.
- Package a downloadable zip under `workspace/factory_generated/upi_dispute_resolution/export_bundles/phase31/`.
- Include the generated application output, generation manifest, Phase 28 architecture-depth inputs summary, Phase 29 deep-structure policy summary, and Phase 30 regeneration/certification-readiness evidence summary.
- Include evidence for no live provider calls, no real secrets, no deployment, no official certification, and mocked or simulated ecosystem integrations only.

Boundary:
- External UPI rails, NPCI/RBI interfaces, banks, PSPs, merchants, notification systems, providers, and other payment ecosystem integrations remain mocked or simulated.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.
- Risky self-evolution, destructive actions, merge, tag, release, promotion, live provider calls, real secrets, deployment, and certification-related claims require separate human approval.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
