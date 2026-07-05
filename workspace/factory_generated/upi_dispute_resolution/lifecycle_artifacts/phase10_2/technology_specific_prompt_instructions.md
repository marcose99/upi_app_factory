# Phase 10.2 Technology-Specific Prompt Instructions — upi_dispute_resolution

## Mandatory instruction for future agents

Before generating application code, tests, design documents, deployment
artifacts, or operations scripts, identify every software technology involved
in the SDLC step.

For each identified technology, state:

- technology name
- role in the SDLC
- exact version if known
- official documentation reference candidate
- best-practice controls applied
- source status
- freshness requirement
- validation method
- gaps or assumptions

## Best-practice application rule

Apply best practices appropriate to each software, framework, library, tool,
language, database, messaging system, workflow engine, testing tool, security
tool, observability tool, build tool, deployment tool, and runtime technology
involved.

## Source rule

If a technology-specific best-practice statement depends on a specific version,
current vendor behavior, current security guidance, or production deployment
rules, do not guess. Use MISSING_OFFICIAL_SOURCE unless the evidence pack
contains a verified source.

## Generated application quality rule

Carry these dimensions into future generated application work:

- reliability
- security
- maintainability
- modularity
- testability
- observability
- auditability
- usability
- performance awareness
- recoverability
- operability
- economic sustainability

## Mock-safe rule

No future agent may introduce live bank, NPCI, RBI, PSP, customer, payment,
notification, or ledger integration without an explicit future production
authorization artifact. Until then, all such interactions remain MOCK_BOUNDARY.
