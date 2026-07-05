# Phase 10 Domain Analysis — upi_dispute_resolution

## Scope

This is a governed, mock-safe, deterministic-first domain model for a UPI
dispute-resolution software factory. It prepares lifecycle artifacts before
any code generation.

The domain is intentionally limited to a mock dispute-resolution application.
It does not connect to real UPI rails, NPCI, RBI, banks, PSPs, TPAPs, customer
systems, or live ledgers. Every external participant must remain behind a
MOCK_BOUNDARY.

## Payment dispute domain concepts

- Customer dispute case
- UPI transaction reference
- Remitter participant
- Beneficiary participant
- PSP / app participant
- Mock NPCI/ODR participant
- Dispute reason
- Failed transaction
- Duplicate debit
- Refund pending
- Status inquiry
- Escalation
- Evidence pack
- Deterministic decision rule
- Human-review queue
- Release evidence

## Regulatory-alignment themes

The factory should reason about regulatory themes without overclaiming:
ODR, failed-transaction turn-around-time awareness, customer-liability
awareness, audit evidence, complaint escalation, security controls,
data minimisation, and operational resilience.

Exact legal interpretation, exact current TAT limits, exact compensation,
official certification status, and production compliance assessment must not
be invented. Use MISSING_OFFICIAL_SOURCE when the official source is absent,
stale, or not parsed into the evidence pack.

## Economics — factory level

Factory economics should be evaluated before code generation:

1. Build cost: prompts, deterministic templates, validators, tests, docs,
   review cycles, and integration work.
2. Run cost: LLM calls where used, local scripts, workflow orchestration,
   storage, trace generation, and validation time.
3. Rework cost: failed generation, missing traceability, weak requirements,
   unclear architecture, and human correction effort.
4. Cost of quality: tests, static checks, policy checks, evidence ledger,
   audit pack, and release-readiness gates.
5. Cost of poor quality: production incidents, rework, unclear ownership,
   audit failure, false claims, and support burden.
6. Switching economics: replaceable model providers, vector stores, policy
   engines, workflow engines, evidence stores, and observability systems.
7. Learning economics: beginner-readable code and debug guides reduce future
   maintenance and onboarding cost.

## Economics — application level

A UPI dispute-resolution application has operational economic drivers:

- manual triage effort per dispute
- aging queue cost
- customer support cost
- refund leakage
- compensation exposure
- false-positive and false-negative decision cost
- complaint re-open cost
- reconciliation effort
- trust/reputation impact
- escalation handling
- incident recovery cost
- audit and evidence production cost

All real economic values must be sourced. Synthetic values must be labelled
SYNTHETIC_DATA. Any unsupported claim about live fee, penalty, compensation,
or ROI must be labelled MISSING_OFFICIAL_SOURCE.

## Quality dimensions

The generated application must carry quality into design rather than bolting
it on later: reliability, security, maintainability, modularity, testability,
observability, explainability, operability, recoverability, performance,
usability, auditability, and controlled extensibility.

## Data classification

- Synthetic dispute request: SYNTHETIC_DATA
- Synthetic participant response: SYNTHETIC_DATA
- Mock policy scenario: SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- Missing current regulatory fact: MISSING_OFFICIAL_SOURCE
- Any bank/NPCI/RBI/external system interaction: MOCK_BOUNDARY
