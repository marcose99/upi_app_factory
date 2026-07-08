<!-- PHASE_11C_GENERATED_APPLICATION_QUALITY_CONTRACT -->
## Phase 11C Generated Application Type and Quality Contract

Labels: GENERATED_APPLICATION_TYPE_BEST_PRACTICES, CODE_QUALITY_REPORTS, UNIT_TESTS, INTEGRATION_TESTS, SCENARIO_COVERAGE, RELEASE_EVIDENCE.

Every relevant agent and prompt must adopt every best practice of the generated application type and every supporting engineering element used to create, validate, release, operate, and maintain it.

Mandatory generated application boundary:
- The primary payment/UPI dispute resolution application must be generated as real, locally runnable software.
- External ecosystem applications and integrations must remain mock/simulated.
- The correct boundary is: real primary UPI/payment application with mock/simulated external ecosystem.
- Do not describe the whole generated application as strictly mock-only.

Mandatory generated application type best practices:
- Use domain-appropriate architecture for a UPI/payment dispute resolution application, including input/output contracts, explicit contracts, validation, idempotency, auditability, error handling, traceability, and deterministic local execution.
- Use technology-specific SDLC best practices for every programming language, framework, library, database, messaging component, workflow component, testing tool, security tool, observability tool, and runtime/deployment component involved.
- Keep code beginner-readable and debug-friendly without weakening production-grade discipline.
- Prefer small cohesive modules, explicit names, typed contracts, clear validation, helpful errors, deterministic behavior, and practical debug guidance.
- Maintain strict separation between business rules, application orchestration, adapters, mock external ecosystem integrations, persistence, validation, and reporting.
- Do not hardcode expected scenario answers unless the artifact is explicitly a deterministic test fixture or golden dataset.

Mandatory quality and evidence artifacts:
- Produce or update code quality report evidence, including lint results, type-check results, formatting/status notes, complexity/maintainability notes where available, and known limitations.
- Produce or update unit test report evidence for pure domain logic, validators, contracts, classifiers, mappers, policies, and deterministic utility functions.
- Produce or update integration test report evidence for the locally runnable primary application boundary, persistence boundaries where present, API/CLI boundaries where present, and mock external ecosystem adapter boundaries.
- Produce or update scenario coverage report evidence for positive, negative, edge, validation-failure, idempotency, retry, timeout, unavailable-mock, unsupported requirement, out-of-scope requirement, audit, governance, and traceability scenarios.
- Produce or update regression test report evidence before release.
- Produce or update security review evidence covering prompt-injection and untrusted-input defenses, PII/secret handling, least-privilege tools, dependency risk, unsafe output handling, and fail-closed behavior.
- Produce or update observability evidence covering structured logs, trace/correlation IDs, metrics, error categories, retry counts, latency, and LLM metrics/expense ledgers.
- Produce release-readiness evidence showing every required quality gate and scenario gate passed before merge/tag.

Mandatory testing expectations:
- Unit tests must cover normal paths, boundary values, invalid inputs, missing fields, duplicate inputs, unsupported values, deterministic classification behavior, and traceability identifiers.
- Integration tests must cover primary application flows against mock/simulated ecosystem adapters and must not call live NPCI, RBI, bank, PSP, payment rail, customer, or production infrastructure.
- Scenario coverage must map each important requirement and capability decision to one or more tests or explicit evidence items.
- Coverage gaps must be reported honestly instead of hidden through broad assertions or hardcoded responses.
- Test data must be synthetic and must not contain real customer data, secrets, credentials, or live regulated identifiers.

Mandatory reporting and governance:
- Every generated or updated code artifact must remain traceable to requirement IDs, capability classification, support-level decision, and validation evidence where applicable.
- Every quality report must identify the command, result, timestamp or run context when available, and artifacts checked.
- Any failed, skipped, xfailed, or not-applicable gate must include a reason and remediation path.
- The final consolidated LLM metrics and expense summary must remain the last LLM-dependent artifact; no additional LLM calls are allowed after the final metrics and expense summary is emitted.
<!-- END_PHASE_11C_GENERATED_APPLICATION_QUALITY_CONTRACT -->
