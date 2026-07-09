# Phase 45 final runbook

This is the final v1.0 candidate consolidation runbook for the governed local
UPI dispute resolution factory.

## Review order

1. Read the final manifest and release gate.
2. Read the final evidence index.
3. Read the architecture, operator portal, and generated application summaries.
4. Run the Phase 45 validator and targeted Phase 45 tests.
5. Run the inherited Phase 28 through Phase 34 validation stack listed in the
   validation summary.
6. Run `python -m ruff check .` and `python -m mypy .`.

## Boundary

The project remains `certification_ready_not_certified`. It does not claim
official certification, regulatory approval, legal sufficiency, live payment
capability, or broad production readiness. Readiness language is limited to
local-readiness evidence.

External UPI rails, banks, NPCI/RBI interfaces, payment rails,
upstream/downstream systems, ODR systems, notification systems, and third-party
services remain mocked or simulated.
