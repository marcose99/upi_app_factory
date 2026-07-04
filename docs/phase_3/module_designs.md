# Phase 3 Module Designs

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

## Modules

- app.disputes.models: typed domain contracts.
- app.disputes.service: local synthetic workflow service.
- app.disputes.router: FastAPI endpoints.
- adapters.mock_upi_switch: synthetic failed transaction source.
- adapters.mock_core_banking: synthetic ledger observations.
- adapters.mock_customer_notification: no-send notification recorder.
- adapters.mock_dispute_evidence_store: in-memory evidence pack store.
