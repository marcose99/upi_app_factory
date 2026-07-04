# v0.5.2 TestClient Warning Fix

Status: PASSED

Evidence labels:

- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MOCK_BOUNDARY
- SYNTHETIC_DATA

## Issue

Pytest was passing but emitted a Starlette TestClient deprecation warning because the test client was using plain `httpx`.

## Fix

Added `httpx2` as a direct project dependency so Starlette/FastAPI TestClient can use the expected modern client path.

## Validation

- pytest completed successfully.
- The previous StarletteDeprecationWarning was not present.
- Ruff passed.
- MyPy passed.
- Phase 1 validator passed.
- Combined Phase 2-5 validator passed.
- Governance validators passed.
- Mock boundary validator passed.
- Evidence and release readiness validators passed.

## Boundary Confirmation

This dependency change does not add or permit any real UPI, NPCI, RBI, bank, PSP, switch, settlement, or customer notification integration.
