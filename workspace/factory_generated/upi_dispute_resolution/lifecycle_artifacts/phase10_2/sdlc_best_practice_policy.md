# Phase 10.2 SDLC Technology Best-Practice Policy — upi_dispute_resolution

## Purpose

Every future generated application artifact must identify the software
technologies involved and follow best practices appropriate to each one.

This applies to:

- programming languages
- frameworks
- libraries
- databases
- messaging systems
- workflow engines
- testing tools
- static-analysis tools
- security tools
- policy-as-code tools
- observability tools
- build tools
- packaging tools
- deployment and runtime technologies
- documentation and data formats

## Mandatory rule

A future agent must not produce generic advice when a technology-specific rule
is required. It must either:

1. use source-backed official documentation,
2. use a project policy already validated by the factory,
3. use USER_PROVIDED_VALUE when the user supplies it,
4. use SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL for mock/demo reasoning, or
5. mark the point MISSING_OFFICIAL_SOURCE.

## Engineering controls

Future generated code and artifacts must prefer:

- small beginner-readable modules
- explicit contracts and schemas
- deterministic validation where practical
- clear error messages
- idempotent scripts
- secure defaults
- least privilege
- dependency and version discipline
- traceable decisions
- tests covering happy and negative paths
- observable request/evidence correlation
- rollback and restore-point planning
- modular ports/adapters to reduce replacement cost

## Economics alignment

Technology choices must consider:

- build cost
- run cost
- review cost
- replacement cost
- vendor lock-in cost
- debugging and onboarding cost
- operational cost
- cost of poor quality
- cost of security or compliance mistakes

Exact monetary claims require official or user-provided data.

## Boundary

This policy does not claim production readiness, certification, official
compliance, or security guarantees.
