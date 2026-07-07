# Phase 13AB — Local Generated Application Capability Certification Matrix

## Purpose

Phase 13AB introduces the local-first certification foundation for generated application capabilities.

Generated capabilities must not be released only because code was produced. Each capability must be checked against a deterministic certification matrix, backed by source-controlled evidence, governed by policy, and held behind a human approval gate.

## Certification mode

- Mode: `LOCAL_FIRST_DETERMINISTIC`
- Live provider calls: disabled
- External ecosystem calls: disabled unless mocked locally
- Human approval before release: required
- Evidence: required for every quality dimension
- Release decision vocabulary:
  - `CERTIFIED_LOCAL`
  - `CERTIFIED_WITH_WARNINGS`
  - `NOT_CERTIFIED`
  - `BLOCKED_BY_POLICY`

## Minimum quality dimensions

1. Unit tests
2. Integration tests
3. Contract/API tests
4. Domain rule tests
5. Negative/error-path tests
6. Boundary/mock ecosystem tests
7. Regression tests
8. Policy/governance tests
9. Audit/evidence tests
10. Type checks
11. Lint/static quality checks
12. Security/static scanning hooks
13. Dependency/supply-chain checks where locally available
14. Performance/smoke/load checks where locally feasible
15. Resilience/idempotency/replay checks
16. Operator handover/runbook checks
17. Capability certification report generation

## Current Phase 13AB decision

Overall status: `CERTIFIED_WITH_WARNINGS`

Phase 13AB adds the certification matrix, policy, audit record, requirement traceability, validator, and tests. Later phases should connect this foundation to generated application release automation so every generated capability receives measured local certification evidence before release.

## Governance rules

- Certification must be local-first and deterministic.
- Certification must not call live LLM providers, payment rails, banks, NPCI/RBI services, or any external ecosystem system.
- Certification must include evidence references for every quality dimension.
- Missing required dimensions block certification.
- Live provider usage without explicit approval maps to `BLOCKED_BY_POLICY`.
- Final release remains human-approval-gated even when local certification passes.

## References

- NIST Secure Software Development Framework SP 800-218: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Software Component Verification Standard: https://owasp.org/www-project-software-component-verification-standard/
- OWASP Application Security Verification Standard: https://owasp.org/www-project-application-security-verification-standard/
- SLSA Supply-chain Levels for Software Artifacts: https://slsa.dev/
