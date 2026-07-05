# Phase 10.3 Implementation Guardrails — upi_dispute_resolution

## Mock-safe boundary

All external payment ecosystem dependencies remain MOCK_BOUNDARY:

- customer app
- remitter bank
- beneficiary bank
- PSP / TPAP
- NPCI / ODR
- RBI source references
- ledger
- reconciliation
- notification
- support system

No Phase 11 implementation may call a real bank, NPCI, RBI, PSP, customer,
payment, notification, or ledger service.

## Deterministic-first rule

Use deterministic rules, schemas, validators, and tests before introducing
LLM behavior. Any future agentic behavior must remain governed by evidence,
traceability, and fail-closed validation.

## Economics rule

Do not invent:

- current UPI volume or value
- bank internal cost per dispute
- support cost
- staffing reduction
- exact ROI
- exact vendor cost
- penalty or compensation exposure beyond source-backed context

Use MISSING_OFFICIAL_SOURCE, USER_PROVIDED_VALUE, or SYNTHETIC_DATA.

## Technology best-practice rule

Every generated implementation artifact must identify the technologies it uses
and apply technology-specific SDLC best practices. If a statement depends on
a version or vendor detail not available in evidence, label it
MISSING_OFFICIAL_SOURCE.

## Quality rule

Generated application work must preserve:

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
