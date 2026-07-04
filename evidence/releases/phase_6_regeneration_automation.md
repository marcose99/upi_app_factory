# Phase 6 Regeneration Automation Evidence

Status: CREATED

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

## Result

Phase 6 added deterministic regeneration automation for the mock dispute application slice.

## Controls

- Regeneration reads governance contracts before writing output.
- Generated output is staged under `workspace/regeneration_runs`.
- Generated manifests include file hashes.
- Regeneration does not call real UPI, NPCI, RBI, bank, PSP, switch, settlement, or customer systems.
- Regeneration preserves MOCK_BOUNDARY and SYNTHETIC_DATA controls.
