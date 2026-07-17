---
app_id: upi_app_factory
product_name: UPI App Factory
repository_id: upi_app_factory
domain: failed_debit_dispute_case_management
runtime_llm_calls_default: 0
real_payment_calls: disabled
data_policy: fictional_only
---

# Failed Debit Requirements

## Actors
- id: ACT-001; name: Payer; description: Fictional customer reporting a debit where no beneficiary credit is visible.
- id: ACT-002; name: Dispute Operations Analyst; description: Reviews timeline, evidence, eligibility, and resolution proposals.
- id: ACT-003; name: Simulated Bank Adapter; description: Local fictional adapter that returns status snapshots without provider calls.

## Use Cases
- id: UC-001; name: Lodge failed debit case; actors: ACT-001, ACT-002; description: Create a dispute for a debit with missing credit using fictional transaction references.
- id: UC-002; name: Validate failed debit eligibility; actors: ACT-002; description: Confirm age, amount, duplicate-case, and transaction-reference eligibility before investigation.
- id: UC-003; name: Resolve failed debit; actors: ACT-002, ACT-003; description: Propose reversal, rejection, or manual review based on deterministic local evidence.

## Bounded Contexts
- id: BC-001; name: Dispute Intake; description: Owns case creation, idempotency, identity abstraction, and request validation.
- id: BC-002; name: Failed Debit Investigation; description: Owns timeline reconstruction, simulated bank status capture, and evidence sufficiency.
- id: BC-003; name: Resolution Evidence; description: Owns decision records, audit lineage, and exportable evidence bundles.

## Commands
- id: CMD-001; name: CreateFailedDebitCase; actors: ACT-002; description: Opens a failed-debit dispute with idempotency and correlation identifiers.
- id: CMD-002; name: AttachDebitEvidence; actors: ACT-002; description: Adds screenshots, bank statement excerpts, or fictional rail status evidence.
- id: CMD-003; name: RecordInvestigationOutcome; actors: ACT-002; description: Records deterministic investigation observations and emits an outcome event.
- id: CMD-004; name: ProposeFailedDebitResolution; actors: ACT-002; description: Proposes reversal, rejection, or manual-review resolution with reason codes.

## Queries
- id: QRY-001; name: GetFailedDebitCase; description: Returns current case state, version, and redacted fictional party references.
- id: QRY-002; name: ListFailedDebitCases; description: Filters failed-debit disputes by state, age bucket, analyst, and resolution status.
- id: QRY-003; name: GetFailedDebitTimeline; description: Returns command, event, evidence, and audit lineage for one case.

## Events
- id: EVT-001; name: FailedDebitCaseCreated; description: Emitted after a case is accepted into the received state.
- id: EVT-002; name: FailedDebitEligibilityValidated; description: Emitted after eligibility invariants pass or fail.
- id: EVT-003; name: FailedDebitEvidenceAttached; description: Emitted when evidence is attached and hash-linked.
- id: EVT-004; name: FailedDebitInvestigationRecorded; description: Emitted after simulated bank status and timeline checks are recorded.
- id: EVT-005; name: FailedDebitResolutionProposed; description: Emitted when resolution policy produces a proposed outcome.

## Aggregates
- id: AGG-001; name: FailedDebitDisputeCase; description: Controls lifecycle, evidence, version, eligibility, and resolution state for one dispute.
- id: AGG-002; name: EvidenceBundle; description: Groups fictional evidence items and their hashes for one failed-debit dispute.

## Invariants
- id: INV-001; name: Fictional data only; description: Cases must not contain real customer, bank, card, or payment-provider data.
- id: INV-002; name: No live provider calls; description: All bank, rail, and notification interactions remain simulated local adapters.
- id: INV-003; name: Idempotent mutation; description: Every command mutation requires idempotency key and correlation identifier.
- id: INV-004; name: Versioned resolution; description: Resolution proposals must reference the case version used by the policy.
- id: INV-005; name: Duplicate failed debit guard; description: A transaction reference may have only one open failed-debit case.

## Workflows
- id: WF-001; name: Intake to validation; description: received -> validated or rejected after duplicate, amount, and reference checks.
- id: WF-002; name: Evidence to investigation; description: validated -> evidence_pending -> investigation when required evidence is present.
- id: WF-003; name: Resolution to closure; description: investigation -> resolution_proposed -> resolved -> closed with audit evidence.

## APIs
- id: API-001; method: POST; path: /v1/disputes; description: Creates a failed-debit dispute with idempotency and correlation headers.
- id: API-002; method: GET; path: /v1/disputes/{dispute_id}; description: Reads a failed-debit dispute with object authorization.
- id: API-003; method: POST; path: /v1/disputes/{dispute_id}/evidence; description: Adds evidence to a failed-debit case.
- id: API-004; method: POST; path: /v1/disputes/{dispute_id}/investigation; description: Records investigation outcome.
- id: API-005; method: POST; path: /v1/disputes/{dispute_id}/resolution; description: Proposes resolution using deterministic policy.

## Data
- id: DATA-001; name: FailedDebitCaseRecord; description: Stores dispute id, transaction reference, money, state, version, timestamps, and redacted party references.
- id: DATA-002; name: FailedDebitEvidenceRecord; description: Stores evidence metadata, content digest, type, source, and append-only audit reference.
- id: DATA-003; name: TransactionalOutboxRecord; description: Stores pending local domain events for deterministic dispatch tests.

## Security
- id: SEC-001; name: Header principal abstraction; description: Uses a fictional local header principal and roles without production identity claims.
- id: SEC-002; name: Object authorization port; description: Every case read and mutation checks analyst access to the dispute.
- id: SEC-003; name: PII-safe logging; description: Logs correlation ids and synthetic references, never raw personal data.
- id: SEC-004; name: Problem JSON errors; description: Validation failures use stable safe application/problem+json-shaped responses.

## Operations
- id: OPS-001; name: Local SQLite persistence; description: Uses standard-library sqlite3 with migrations, transactions, foreign keys, and integrity checks.
- id: OPS-002; name: Mock ecosystem boundary; description: Real payment calls disabled, runtime LLM calls default to zero, and provider calls are local simulations.
- id: OPS-003; name: Metrics and readiness; description: Provides local health, readiness, and JSON metric counters without external telemetry dependency.

## Evidence
- id: EVD-001; name: Requirement IR traceability; description: Compiler output maps every requirement id to source document, line, and canonical hash.
- id: EVD-002; name: Failed-debit test plan; description: Tests cover eligibility, duplicate guard, evidence sufficiency, resolution policy, and audit lineage.
- id: EVD-003; name: Governance report; description: Report records mock-only controls, no certification claim, and deterministic validation results.

## Dependencies
- id: DEP-001; name: Python standard library; description: pathlib, json, hashlib, sqlite3, argparse, and unittest-compatible pytest tests.
- id: DEP-002; name: Existing FastAPI environment; description: Available to runtime phases without adding mandatory external databases or brokers.
