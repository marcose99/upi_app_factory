# Phase 45 final v1 candidate consolidation prompt

Consolidate the final v1.0 candidate for the governed local UPI dispute
resolution factory. This is the professional stopping point for the local
candidate, not an official certification, production release, deployment, merge,
push, or release-label creation step.

Mandatory inputs:
- `factory/operator_portal/final_v1_candidate_consolidation.py`
- `scripts/generate_phase45_final_v1_candidate_consolidation.py`
- `scripts/validate_phase45_final_v1_candidate_consolidation.py`
- `policies/phase45_final_v1_candidate_policy.json`
- Phase 28 through Phase 34 generated application and operator portal evidence
- Phase 44 release evidence bundle
- Phase 45 lifecycle artifacts under
  `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase45/`

Required outputs:
- Final v1 candidate manifest and release gate.
- Final runbook, README updates, architecture summary, operator portal summary,
  generated app summary, validation summary, limitation statement, next-roadmap,
  final evidence index, and final local demo instructions.
- Prepared future release label text:
  `v1.0.0-local-governed-upi-factory-candidate`.

Execution rules:
- Preserve `certification_ready_not_certified`.
- Keep readiness language scoped to local-readiness evidence only.
- Do not call live providers.
- Do not create real secrets.
- Do not deploy, merge, create release labels, push, or create generated export
  bundle ZIP files.
- Do not claim official certification, approval, live payment capability, legal
  sufficiency, or broad production readiness.
- Keep UPI rails, banks, NPCI/RBI interfaces, payment rails,
  upstream/downstream systems, ODR systems, notification systems, customer
  systems, and third-party services mocked or simulated.
- Do not fake validation success.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
