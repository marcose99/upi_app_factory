# Phase 11C Generated Application Quality Prompt Contract

This deterministic contract requires relevant prompt source files to instruct agents to adopt every best practice of the generated application type and every supporting quality/evidence element.

## Boundary

- Primary payment/UPI dispute resolution application: real, locally runnable software.
- External ecosystem applications and integrations: mock/simulated only.
- Correct boundary: real primary UPI/payment application with mock/simulated external ecosystem.

## Required evidence families

- Code quality report evidence.
- Unit test report evidence.
- Integration test report evidence.
- Scenario coverage report evidence.
- Regression report evidence.
- Security review evidence.
- Observability evidence.
- Release-readiness evidence.

## Scenario coverage expectations

Positive, negative, edge, validation-failure, idempotency, retry, timeout, unavailable-mock, unsupported requirement, out-of-scope requirement, audit, governance, and traceability scenarios must be represented by tests or explicit evidence.

## Prompt-source scope repair

Phase 11C validators intentionally check relevant prompt source files only. Governance reference documents, ADR templates, project charters, generated review reports, and generated Phase 11C evaluation artifacts are not treated as prompt source files.
