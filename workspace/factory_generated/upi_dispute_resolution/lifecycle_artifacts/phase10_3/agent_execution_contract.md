# Phase 10.3 Agent Execution Contract — upi_dispute_resolution

## Purpose

This contract governs how Phase 11 and later implementation agents may generate
the mock UPI dispute-resolution application.

## Mandatory agent behavior

Every future implementation agent must:

1. Read the generation input manifest before changing files.
2. Follow Phase 10 requirements, architecture, HLD, LLD, WBS, and traceability.
3. Use Phase 10.1 source registry and source gap policy.
4. Use Phase 10.2 SDLC technology best-practice policy.
5. Preserve MOCK_BOUNDARY for banks, NPCI, RBI, PSPs, customer systems,
   ledgers, notification systems, reconciliation systems, and ODR systems.
6. Label unsupported regulatory, economic, technology, or operational facts
   as MISSING_OFFICIAL_SOURCE.
7. Use SYNTHETIC_DATA for demo data.
8. Keep generated code beginner-readable and debug-friendly.
9. Generate tests and validation scripts alongside implementation.
10. Prefer deterministic logic before agentic or LLM-based behavior.
11. Avoid false claims of certification, compliance, production readiness, or legal-advice status.

## Role-specific expectations

- implementation_planner_agent: break WBS tasks into safe code steps.
- contract_model_agent: create explicit schemas and validation boundaries.
- mock_adapter_agent: create mock external participant adapters only.
- service_logic_agent: implement deterministic dispute workflow logic.
- test_generation_agent: generate happy-path, negative-path, and boundary tests.
- security_review_agent: check secrets, unsafe inputs, and privacy boundaries.
- observability_agent: add traceable request/evidence identifiers.
- documentation_agent: write beginner-readable usage and debug guides.
- validation_agent: run deterministic validators and tests.
- release_readiness_agent: verify restore points, gates, and no false claims.

## Stop conditions

An agent must stop and produce a validation failure if:

- an upstream required artifact is missing
- a required validation report fails
- a live payment integration is introduced
- a real customer data requirement is introduced
- a false compliance/certification claim appears
- an economic or regulatory value is invented
- a technology-specific best-practice claim lacks source or gap label
