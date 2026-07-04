# Phase 6: Regeneration Automation

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

## Purpose

Phase 6 introduces deterministic regeneration of the mock dispute application slice.

## Regeneration Model

The factory uses canonical templates under `factory/templates/mock_dispute_app` and validates governance contracts before writing generated output.

The generator writes into:

```text
workspace/regeneration_runs/<run_id>/generated
```

This preserves safety because generated output is staged first and does not overwrite the main application.

## Governance Inputs

The generator validates:

- Phase 2 requirements contract
- Phase 2 mock ecosystem contract
- Phase 3 architecture design contract

## Boundary Position

No real UPI, NPCI, RBI, bank, PSP, switch, settlement, or customer notification integration is allowed.

All generated external boundaries remain MOCK_BOUNDARY and all generated business data remains SYNTHETIC_DATA.
