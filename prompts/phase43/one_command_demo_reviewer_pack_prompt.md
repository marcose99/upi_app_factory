# Phase 43 one-command demo reviewer pack prompt

Create a reviewer-focused one-command demo pack for the generated UPI dispute
resolution factory application. The command must either run only bounded safe
local checks or print exact staged commands when full automation would require a
long-running process.

Mandatory inputs:
- `scripts/run_phase43_one_command_demo_reviewer_pack.py`
- `scripts/validate_phase43_one_command_demo_reviewer_pack.py`
- `policies/phase43_one_command_demo_reviewer_pack_policy.json`
- Phase 42 generated app local run-pack scripts
- Phase 34 governed validation runner evidence
- Phase 43 lifecycle artifacts under
  `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/`

Reviewer pack requirements:
- Explain what the factory does.
- Explain how to run it with one command and with explicit staged commands.
- Identify evidence to inspect.
- Identify what is intentionally mocked or simulated.
- Preserve the `certification_ready_not_certified` boundary.
- List known limitations.

Execution rules:
- The default one-command path prints exact staged commands when starting a local
  server would be unsafe to automate.
- Bounded safe checks may run local smoke tests and local run-pack validation.
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
