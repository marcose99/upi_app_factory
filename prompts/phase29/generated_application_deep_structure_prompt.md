# Phase 29 generated application deep-structure prompt

Generate the primary UPI dispute resolution application as real, locally runnable software with the Phase 28 architecture-depth blueprint as an explicit generator input. The generator must emit a professional layered `generated_application/` structure before any generated application may be described as successful.

Mandatory generator inputs:
- `factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json`
- `policies/phase28_generated_application_architecture_depth_policy.json`
- `prompts/phase28/generated_application_architecture_depth_prompt.md`

Mandatory emitted structure:
- `generated_application/app/domain/entities.py`
- `generated_application/app/domain/value_objects.py`
- `generated_application/app/domain/policies.py`
- `generated_application/app/domain/domain_events.py`
- `generated_application/app/domain/exceptions.py`
- `generated_application/app/application/commands.py`
- `generated_application/app/application/queries.py`
- `generated_application/app/application/services.py`
- `generated_application/app/application/unit_of_work.py`
- `generated_application/app/application/ports.py`
- `generated_application/app/infrastructure/persistence/repositories.py`
- `generated_application/app/infrastructure/persistence/migrations/`
- `generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py`
- `generated_application/app/infrastructure/persistence/postgres_unit_of_work.py`
- `generated_application/app/infrastructure/persistence/outbox.py`
- `generated_application/app/infrastructure/persistence/idempotency_store.py`
- `generated_application/app/interfaces/api/main.py`
- `generated_application/app/interfaces/api/routers/`
- `generated_application/app/interfaces/api/schemas.py`
- `generated_application/app/interfaces/api/error_handlers.py`
- `generated_application/app/interfaces/cli/`
- `generated_application/app/interfaces/workers/`
- `generated_application/app/observability/logging.py`
- `generated_application/app/observability/metrics.py`
- `generated_application/app/observability/tracing.py`
- `generated_application/app/security/pii_redaction.py`
- `generated_application/app/security/input_validation.py`
- `generated_application/app/tests/unit/`
- `generated_application/app/tests/integration/`
- `generated_application/app/tests/contract/`
- `generated_application/app/tests/negative/`
- `generated_application/app/tests/resilience/`
- `generated_application/app/tests/security/`
- `generated_application/app/tests/performance/`

Mandatory generated-application capabilities:
- Explicit domain entities, value objects, policies, domain events, and typed domain exceptions.
- Explicit dispute lifecycle state machine with allowed transitions, guarded invalid transitions, terminal states, idempotent replay behavior, and audit-safe events.
- Application services, commands, queries, repository ports, and unit-of-work abstractions.
- SQLite-first local persistence boundary with migration discipline, outbox, audit trail, and idempotency store.
- API contract schemas, structured error handling, input validation, PII redaction, structured logging, metrics, and tracing-ready hooks.
- Unit, integration, contract, negative, resilience, security, and performance-smoke test obligations.

Boundary:
- External UPI rails, NPCI/RBI interfaces, banks, PSPs, merchants, notification systems, providers, and other ecosystem integrations remain mocked or simulated.
- The posture remains `certification_ready_not_certified`, meaning certification-ready-not-certified.
- Do not claim official certification, official compliance, NPCI approval, RBI approval, bank approval, production readiness, live payment capability, or legal sufficiency.
- Risky self-evolution, destructive actions, merge, tag, release, promotion, live provider calls, and certification-related claims require human approval.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}

{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
