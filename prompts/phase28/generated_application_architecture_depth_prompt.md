# Phase 28 generated application architecture-depth prompt

Generate architecture first. Before the generated UPI dispute resolution application can be considered successful, create or update every mandatory architecture-depth artifact:

- `architecture_blueprint.md`
- `domain_model.md`
- `bounded_contexts.md`
- `dispute_state_machine.md`
- `api_contracts.md`
- `data_contracts.md`
- `security_model.md`
- `observability_model.md`
- `test_obligation_matrix.md`
- `self_evolution_backlog.json` or `self_evolution_backlog.md`
- `certification_readiness_boundary.md`

The architecture blueprint must move the generated application toward the governed layered structure defined in `factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json`.

Generation order:

1. Define domain model, bounded contexts, state machine, API contracts, data contracts, security model, observability model, and test obligation matrix.
2. Validate import-boundary expectations before expanding business logic.
3. Validate dispute state-machine expectations before claiming workflow success.
4. Keep external UPI, bank, NPCI, PSP, ODR, payment rail, notification, ledger, regulator-facing, and provider integrations mocked or simulated.
5. Produce a self-evolution backlog that can propose improvements but marks risky changes as human-approved only.
6. State the boundary as `certification_ready_not_certified`; do not claim official certification, official compliance, production readiness, bank approval, NPCI approval, RBI approval, or legal sufficiency.

The generated application remains a real locally runnable primary UPI/payment dispute application. Surrounding ecosystem integrations remain mock/simulated unless a later separately approved phase changes that boundary.

## Inherited prompt governance contracts

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}
{{ include: prompts/_contracts/generated_application_quality_contract.md }}
{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
