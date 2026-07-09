# Phase 44 release evidence bundle prompt

Create a reviewable release evidence bundle for the governed UPI dispute
resolution factory. The bundle must package governance, validation, generated
application evidence, and operator portal evidence without creating a ZIP export.

Mandatory inputs:
- `factory/operator_portal/release_evidence_bundle.py`
- `scripts/generate_phase44_release_evidence_bundle.py`
- `scripts/validate_phase44_release_evidence_bundle.py`
- `policies/phase44_release_evidence_bundle_policy.json`
- Phase 28 through Phase 34 generated application and operator portal evidence
- Phase 43 one-command demo reviewer pack evidence
- Phase 44 lifecycle artifacts under
  `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/`

Bundle requirements:
- Include manifests, policy summaries, validation summaries, evidence index, run
  instructions, and boundary statements.
- Include generated application evidence and operator portal evidence.
- Include SBOM or supply-chain evidence only when supported tools are locally
  available; otherwise record unavailable status truthfully.
- Preserve `certification_ready_not_certified`.
- Keep readiness language scoped to local-readiness evidence only.

Execution rules:
- Do not call live providers.
- Do not create real secrets.
- Do not deploy, merge, tag, push, or create generated export bundle ZIP files.
- Do not claim official certification, approval, live payment capability, legal
  sufficiency, or broad production readiness.
- Keep external ecosystem integrations mocked or simulated.
- Do not fake validation success.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
