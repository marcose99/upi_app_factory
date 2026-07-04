# Phase 3 Architecture Decision

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

## Decision

Use lightweight FastAPI modules with replaceable mock adapters.

## Reason

This fits the current local-first stage while keeping production discipline and mock boundaries.
