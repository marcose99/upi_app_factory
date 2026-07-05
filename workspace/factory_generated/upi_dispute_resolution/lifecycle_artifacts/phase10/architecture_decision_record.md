# Architecture Decision Record — Phase 10 Planning Pipeline

## Status

Accepted for mock project evolution.

## Context

FactoryFromNothing / upi_dispute_resolution needs a requirement-to-architecture-to-plan
pipeline before code generation. Previous phases established governance,
mock boundaries, regeneration, evidence, prompt quality, role simulation,
workflow orchestration, quality dimensions, and payment regulatory alignment.

The next phase must create structured lifecycle artifacts and validate them
before code is generated.

## Decision

Use a governed modular monolith with replaceable ports/adapters.

## Justification

This architecture is selected because it:

- keeps deterministic generation as the default
- remains beginner-readable and debug-friendly
- supports future agentic replacement of individual planners
- avoids heavy infrastructure too early
- keeps governance evidence close to the generated artifacts
- makes economics explicit before implementation
- avoids false compliance or certification claims
- preserves MOCK_BOUNDARY around all external payment participants

## Economic rationale

The selected option reduces immediate build and run cost compared with an
event-driven microservice topology while avoiding the future rigidity of a
single hard-coded generator. It improves cost-to-change through module
contracts and limits LLM/model/tool spend by reserving non-deterministic
reasoning for future controlled extension points.

At application level, the design supports later measurement of manual triage
cost, case aging, compensation exposure, re-open rate, false-positive cost,
false-negative cost, reconciliation effort, and support workload. No real
monetary value is asserted without a source. Unsupported economic claims must
be labelled MISSING_OFFICIAL_SOURCE.

## Consequences

Positive:

- Faster implementation of Phase 10.
- Strong deterministic validation.
- Clear traceability before coding.
- Easier demo regeneration.
- Easier future migration to agent/workflow services.

Negative:

- Not a fully distributed enterprise platform yet.
- Requires ongoing discipline to avoid hard-coded business conclusions.
- Some enterprise workflow behavior remains a
  SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL.

## Compliance posture

This ADR supports regulatory alignment and audit readiness as engineering
practices. It does not claim official RBI/NPCI compliance certification,
legal advice, or production readiness.

## Honesty labels

MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY,
SYNTHETIC_DATA
