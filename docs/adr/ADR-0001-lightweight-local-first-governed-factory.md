# ADR-0001: Lightweight Local-First Governed Factory Baseline

Status: Accepted

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

## Context

The project is a governed local-first software factory for a mock-safe UPI failed transaction and dispute resolution case management application.

The current phase intentionally avoids heavyweight enterprise infrastructure. The factory must be easy to run on a local Ubuntu laptop while preserving production-grade engineering discipline.

## Options Considered

### Option A: Heavy enterprise platform from day one

Pros:

- Closer to large enterprise deployment style.
- More built-in operational features.

Cons:

- Too much setup and configuration for the current phase.
- Slower iteration.
- Higher chance of tool friction before the factory behavior is proven.

### Option B: Lightweight local-first platform with modular adapters

Pros:

- Faster iteration on governed agent behavior.
- Easier to validate locally.
- Keeps OpenAI as model provider while allowing later adapter replacement.
- Supports future migration to Kubernetes, Temporal, managed databases, policy engines, and enterprise observability.

Cons:

- Some enterprise capabilities start as disciplined local substitutes.
- More explicit care is needed to preserve audit and governance discipline.

### Option C: Manual scripts only, no factory structure

Pros:

- Simple for one-off generation.

Cons:

- Does not meet the long-term factory vision.
- Weak auditability and repeatability.
- Agents cannot be governed effectively.

## Decision

Choose Option B: lightweight local-first platform with modular adapters.

## Consequences

The factory will use small, replaceable components first. Every external payment, bank, customer notification, switch, settlement, or evidence dependency must remain mocked.

## Mock Boundary Impact

No real UPI/NPCI/RBI/bank/PSP/payment-switch/settlement integration is allowed in this baseline. All such systems are represented only through mock adapters and synthetic data.

## Validation Impact

Every phase must pass code validation, governance validation, mock-boundary validation, evidence validation, release-readiness validation, and phase-specific validation.
