# Phase 28: Generated Application Architecture Depth Blueprint

Phase 28 makes architecture-depth evidence a required precondition for future generated UPI dispute resolution applications. A generated application is not considered successful until the factory can validate the required architecture, domain, design, engineering, security, observability, testing, self-evolution, and certification-boundary artifacts.

This phase does not rewrite generated application business logic, perform live provider calls, deploy, create real secrets, merge, tag, release, push, or claim official certification.

## Required generated-application artifacts

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

## Architecture-depth gate

Gate: `PHASE28-GA-ARCHITECTURE-DEPTH-GATE`

The gate blocks generated-application success claims unless every required architecture-depth artifact exists and the artifacts define:

- target layered package structure;
- import-boundary expectations;
- dispute state-machine expectations;
- API and data contracts;
- PII, secret, and input-validation controls;
- structured logging, metrics, tracing, correlation IDs, and audit evidence;
- positive, negative, contract, security, resilience, replay, audit, and performance-smoke test obligations;
- self-evolution proposals with risky changes human-approved;
- certification-ready-not-certified boundary.

## Target structure

Future generated applications must move toward:

```text
generated_application/
  app/
    domain/
      entities.py
      value_objects.py
      policies.py
      domain_events.py
      exceptions.py
    application/
      commands.py
      queries.py
      services.py
      unit_of_work.py
      ports.py
    infrastructure/
      persistence/
      repositories.py
      migrations/
      sqlite_unit_of_work.py
      postgres_unit_of_work.py
      outbox.py
      idempotency_store.py
    interfaces/
      api/
        main.py
        routers/
        schemas.py
        error_handlers.py
      cli/
      workers/
    observability/
      logging.py
      metrics.py
      tracing.py
    security/
      pii_redaction.py
      input_validation.py
    tests/
      unit/
      integration/
      contract/
      negative/
      resilience/
      security/
      performance/
```

## Boundary

The primary generated application remains real and locally runnable. External UPI, bank, NPCI, PSP, ODR, payment rail, notification, ledger, regulator-facing, and third-party provider integrations remain mocked or simulated. The factory may prepare certification-readiness evidence, but it does not certify the application.
