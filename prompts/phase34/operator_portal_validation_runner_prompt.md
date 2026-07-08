# Phase 34 operator portal governed validation runner prompt

Add a lightweight local operator portal validation-runner service for the generated UPI dispute resolution factory application. The runner must execute only approved local validation commands and produce truthful structured evidence for the operator portal.

Mandatory inputs:
- `factory/operator_portal/validation_runner.py`
- `scripts/run_phase34_operator_portal_validation_runner.py`
- `scripts/validate_phase34_operator_portal_validation_runner.py`
- `policies/phase34_operator_portal_validation_runner_policy.json`
- Phase 28 through Phase 33 validation commands and lifecycle artifacts
- Phase 34 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase34/`

Runner rules:
- Use an explicit allowlist of approved validation commands.
- Support `dry-run` mode that lists approved commands without execution.
- Execute commands with a controlled working directory.
- Capture command id, command vector, return code, status, stdout/stderr preview, and duration where practical.
- Stop on first failure by default unless an explicit collect-all mode is requested.
- Produce a structured JSON run report under the Phase 34 lifecycle artifact directory.
- The dashboard must report Phase 34 run report availability truthfully and must not fake validation success.
- The runner must never execute arbitrary command strings.
- The runner must never use live providers, real secrets, deployment, merge, tag, or push actions.
- Keep external ecosystem integrations mocked or simulated.

Boundary:
- No live provider calls.
- No real secrets or credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
