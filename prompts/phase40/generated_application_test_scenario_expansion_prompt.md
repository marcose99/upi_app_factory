# Phase 40 generated application test scenario expansion prompt

Expand generated application test scenarios and expected outputs for realistic delivery-grade local validation.

Mandatory inputs:
- `workspace/factory_generated/upi_dispute_resolution/generated_application/`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/tests/scenario_catalog/phase40_scenario_catalog.json`
- `policies/phase40_generated_application_test_scenario_expansion_policy.json`
- Phase 40 lifecycle artifacts under `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase40/`
- `scripts/run_phase40_generated_application_scenario_report.py`
- `scripts/validate_phase40_generated_application_test_scenario_expansion.py`
- `tests/test_phase40_generated_application_test_scenario_expansion.py`

Implementation rules:
- Add a scenario catalog covering positive, negative, edge, contract, replay, audit, resilience, security, and performance-smoke categories.
- Include expected outputs for every scenario and trace each scenario to generated app endpoints, modules, or local behavior.
- Add a local scenario runner/report that executes the generated FastAPI app through in-process ASGI transport only.
- Keep UPI rails, banks, NPCI/RBI interfaces, payment rails, upstream/downstream systems, and third-party services mocked or simulated.
- Do not fake success. Scenario reports must show failed status when observed behavior does not match expected output.
- Do not create real credentials or real secrets.
- Do not enable deployment, merge, tag, or push actions.
- Do not create generated export bundle ZIP files.

Boundary:
- Local-readiness only for generated application scenario validation.
- No live provider calls.
- No real credentials.
- No deployment, merge, tag, or push.
- The posture remains `certification_ready_not_certified`.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, broad production readiness, live payment capability, or legal sufficiency.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
