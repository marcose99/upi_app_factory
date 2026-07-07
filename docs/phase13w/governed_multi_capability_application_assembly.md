# Phase 13W — Governed multi-capability application assembly

Phase 13W moves the factory from single generated capabilities to a small generated local application composed of multiple governed capabilities.

The phase assembles:

1. Evidence upload validation.
2. SLA triage and escalation routing.

Governance guarantees:

- Source-controlled assembly policy.
- Requirement-to-capability-to-test traceability.
- Repository-level pytest import isolation for generated tests.
- Mock-only external ecosystem boundary.
- Human release approval before merge/tag/release.
- Deterministic local execution; no OpenAI key is required in this phase.

Future OpenAI-backed mode must use externally injected secrets and must emit prompt, response, model, token/cost, policy, and traceability evidence.


## Runtime type-hint and dynamic import policy

Phase 13W records a governance hardening lesson: dynamically loaded factory modules must be registered in `sys.modules` before execution when downstream orchestration frameworks evaluate runtime type hints. This prevents framework-specific schema evaluation failures while preserving deterministic local execution and future adapter portability.
