# Phase 30 deep generated application regeneration prompt

Run a governed local regeneration of the UPI dispute resolution generated application with the Phase 29 deterministic generator. The result must prove emitted generated application structure and governance evidence, not only the generator templates or documentation.

Mandatory inputs:
- `factory/generators/mock_dispute_app_generator.py`
- `factory/templates/mock_dispute_app/template_manifest.v1.json`
- `policies/phase30_deep_generated_application_regeneration_policy.json`
- `policies/phase29_generated_application_deep_structure_policy.json`
- `factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json`
- `policies/phase28_generated_application_architecture_depth_policy.json`
- `prompts/phase28/generated_application_architecture_depth_prompt.md`

Regeneration rules:
- Regenerate only into a controlled temporary or Phase 30 evidence output location.
- Do not destructively replace the existing generated workspace.
- Verify the generated manifest records Phase 28 architecture-depth inputs and the Phase 29 deep-structure policy.
- Verify emitted modules include domain, application, infrastructure, interfaces, observability, security, and tests.
- Verify certification-readiness test obligations include unit, integration, contract, negative, resilience, security, performance-smoke, replay, and audit tests.

Boundary:
- External UPI rails, NPCI/RBI interfaces, banks, PSPs, merchants, notification systems, providers, and other payment ecosystem integrations remain mocked or simulated.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.
- Risky self-evolution, destructive actions, merge, tag, release, promotion, live provider calls, and certification-related claims require human approval.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
