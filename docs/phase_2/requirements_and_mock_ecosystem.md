# Phase 2: Requirements and Mock Ecosystem

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

## Purpose

Define requirements for a mock-safe UPI-like failed transaction and dispute case workflow.

This is a synthetic enterprise workflow model, not an official UPI, NPCI, RBI, bank, PSP, switch, or settlement implementation.

## Mock Ecosystem

- Mock UPI Switch
- Mock Core Banking Ledger
- Mock Customer Notification Gateway
- Mock Dispute Evidence Store

## Lifecycle

FAILED_TRANSACTION_OBSERVED -> DISPUTE_CASE_CREATED -> EVIDENCE_PENDING -> IN_REVIEW -> RESOLVED -> CLOSED
