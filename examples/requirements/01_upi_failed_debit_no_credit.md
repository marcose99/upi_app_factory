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

UPI failed debit sample for a beneficiary-not-credited dispute workflow.

## Actors
- id: ACT-001; name: Payer; description: Fictional customer reporting a debit where no beneficiary credit is visible.
- id: ACT-002; name: Dispute Operations Analyst; description: Reviews evidence, eligibility, and resolution proposals.
- id: ACT-003; name: Simulated Bank Adapter; description: Local fictional adapter that returns status snapshots without provider calls.

## Use Cases
- id: UC-001; name: Lodge failed debit case; actors: ACT-001, ACT-002; description: Create a dispute for a debit with missing credit using fictional transaction references.
- id: UC-002; name: Validate failed debit eligibility; actors: ACT-002; description: Confirm amount, duplicate-case, and transaction-reference eligibility before investigation.
- id: UC-003; name: Resolve failed debit; actors: ACT-002, ACT-003; description: Propose reversal, rejection, or manual review from deterministic local evidence.

## Bounded Contexts
- id: BC-001; name: Dispute Intake; description: Owns case creation, idempotency, identity abstraction, and request validation.
- id: BC-002; name: Failed Debit Investigation; description: Owns timeline reconstruction, simulated bank status capture, and evidence sufficiency.
- id: BC-003; name: Resolution Evidence; description: Owns decision records, audit lineage, and exportable evidence bundles.

## Commands
- id: CMD-001; name: CreateFailedDebitCase; actors: ACT-002; description: Opens a failed-debit dispute with idempotency and correlation identifiers.
- id: CMD-002; name: AttachDebitEvidence; actors: ACT-002; description: Adds fictional evidence observations and content digests.
- id: CMD-003; name: RecordInvestigationOutcome; actors: ACT-002; description: Records deterministic investigation observations and emits an outcome event.
- id: CMD-004; name: ProposeFailedDebitResolution; actors: ACT-002; description: Proposes a resolution with reason codes and human-review controls.

## Queries
- id: QRY-001; name: GetFailedDebitCase; description: Returns current case state, version, and redacted fictional party references.
- id: QRY-002; name: ListFailedDebitCases; description: Filters failed-debit disputes by state, age bucket, analyst, and resolution status.
- id: QRY-003; name: GetFailedDebitTimeline; description: Returns command, event, evidence, and audit lineage for one case.

## Events
- id: EVT-001; name: FailedDebitCaseCreated; description: Emitted after a case is accepted into the received state.
- id: EVT-002; name: FailedDebitEligibilityValidated; description: Emitted after eligibility invariants pass or fail.
- id: EVT-003; name: FailedDebitEvidenceAttached; description: Emitted when evidence is attached and hash-linked.
- id: EVT-004; name: FailedDebitInvestigationRecorded; description: Emitted after simulated status and timeline checks are recorded.
- id: EVT-005; name: FailedDebitResolutionProposed; description: Emitted when resolution policy produces a proposed outcome.

## Aggregates
- id: AGG-001; name: FailedDebitDisputeCase; description: Controls lifecycle, evidence, version, eligibility, and resolution state for one dispute.
- id: AGG-002; name: EvidenceBundle; description: Groups fictional evidence items and hashes for one failed-debit dispute.

## Invariants
- id: INV-001; name: Fictional data only; description: Cases must not contain real customer, bank, card, or payment-provider data.
- id: INV-002; name: No live provider calls; description: All bank, rail, and notification interactions remain simulated local adapters.
- id: INV-003; name: Idempotent mutation; description: Every command mutation requires an idempotency key and correlation identifier.
- id: INV-004; name: Versioned resolution; description: Resolution proposals must reference the case version used by the policy.
- id: INV-005; name: Duplicate failed debit guard; description: A transaction reference may have only one open failed-debit case.

## Workflows
- id: WF-001; name: Intake to validation; description: received -> validated or rejected after duplicate, amount, and reference checks.
- id: WF-002; name: Evidence to investigation; description: validated -> evidence_pending -> investigation when required evidence is present.
- id: WF-003; name: Resolution to closure; description: investigation -> resolution_proposed -> resolved -> closed with audit evidence.

## APIs
- id: API-001; method: GET; path: /health; description: Returns local service health without external provider access.
- id: API-002; method: GET; path: /ready; description: Returns readiness for local deterministic operation.
- id: API-003; method: GET; path: /openapi.json; description: Publishes the generated OpenAPI contract.
- id: API-004; method: POST; path: /v1/disputes; description: Creates a failed-debit dispute with idempotency and correlation headers.
- id: API-005; method: GET; path: /v1/disputes/{dispute_id}; description: Reads a failed-debit dispute with object authorization.

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

## Document control

- Requirement ID: `upi_failed_debit_no_credit.requirements.v1`
- Intended application ID: `upi_failed_debit_no_credit`
- Scenario class: Payment operations case management
- Execution posture: local, deterministic, mock-safe, human-gated
- Data posture: fictional test data only
- Production posture: not production-ready
- Certification posture: certification-ready-not-certified

## 1. Problem statement

A payer reports that the account was debited, but the beneficiary did not receive the funds. Operations teams need a controlled case workflow that preserves transaction evidence, avoids duplicate compensation, tracks investigation state, and escalates uncertainty.

## 2. Business objective

Engineer a locally runnable, production-shaped reference application that
demonstrates governed intake, validation, case processing, idempotency,
explainable decisions, human escalation, audit evidence, operational health,
and independent testing. The application must not perform a real payment,
refund, reversal, account action, network instruction, or regulatory filing.

## 3. Users and responsibilities

- Payer/customer
- Customer-support agent
- Dispute-operations analyst
- Approver/supervisor
- Audit and compliance reviewer

All consequential classifications and final dispositions remain accountable to
an authorised human operator.

## 4. Authoritative inputs

The application shall accept only fictional demonstration data:

- A client-supplied idempotency key.
- A fictional transaction or alert reference.
- A positive amount expressed in minor currency units where relevant.
- A reason or complaint summary.
- Optional fictional evidence observations.
- Actor and correlation identifiers suitable for an audit trace.

The service shall reject missing mandatory values, malformed identifiers,
negative or zero amounts, oversized input, unsupported state transitions, and
obvious credential or secret material.

## 5. Required outputs

- A unique case identifier.
- Current case state and state-transition history.
- Validation and classification reason codes.
- Evidence-completeness status.
- Human-escalation status and rationale.
- Redacted audit events and correlation identifiers.
- Stable API responses and error contracts.
- Health, readiness, OpenAPI, and local API documentation.
- Test reports, requirements traceability, and checksummed evidence.

## 6. End-to-end workflow

1. Receive a complaint with a fictional transaction reference.
2. Validate mandatory fields and redact sensitive values from logs.
3. Check a mock transaction-status adapter.
4. Create an idempotent dispute case.
5. Classify the case as pending, failed, reversed, or uncertain.
6. Route uncertain or high-value cases to human review.
7. Record every decision and evidence reference.
8. Close only after a mock outcome and reviewer decision are recorded.

## 7. Business and safety rules

- A repeated idempotency key must return the original case.
- No automatic customer credit or payment reversal is allowed.
- Missing or contradictory evidence must produce human escalation.
- The service must distinguish debit, beneficiary credit, reversal, and unknown states.

Additional mandatory rules:

1. Repeated requests with the same idempotency key and equivalent payload must
   return the original result.
2. Reuse of an idempotency key with a conflicting payload must fail closed.
3. Logs and evidence must not contain secrets, real customer data, full account
   identifiers, PINs, passwords, tokens, or API keys.
4. All external bank, PSP, NPCI, issuer, acquirer, merchant, notification, and
   payment-rail interactions must use local deterministic mocks.
5. Unsupported regulatory, compliance, certification, or production-readiness
   claims must be rejected.
6. Low-confidence, contradictory, incomplete, or high-impact decisions must be
   escalated to a human reviewer.

## 8. Required architecture

Use logically separated modules for:

- Domain entities, value objects, invariants, and state transitions.
- Application services and use cases.
- Ports/interfaces for persistence, idempotency, audit, and external mocks.
- Infrastructure adapters using local in-memory or SQLite-backed test stores.
- FastAPI interfaces with typed request/response models.
- Configuration and safety-boundary enforcement.
- Tests and evidence generation.

The implementation should remain replaceable, testable, and free from hidden
network dependencies.

## 9. API expectations

Minimum interfaces:

- `GET /health`
- `GET /ready`
- `GET /openapi.json`
- A case-creation endpoint using an idempotency key.
- A case-inquiry endpoint using the generated case identifier.

API errors must be structured and must distinguish validation failure,
not-found, idempotency conflict, policy refusal, and internal inconsistency.

## 10. Data and audit expectations

- Store only fictional data.
- Mask or tokenise sensitive-looking identifiers.
- Preserve a timestamped append-only audit history for the demonstration.
- Include actor, action, reason code, correlation ID, and evidence digest.
- Do not log complete request bodies before redaction.
- Make reset and retention behaviour explicit.
- Keep generated evidence inside the isolated run workspace.

## 11. Reliability and observability

- Deterministic startup and shutdown.
- Health and readiness probes.
- Structured logs with correlation IDs.
- Explicit exception handling.
- No silent retries of consequential actions.
- Bounded retries only for safe mock reads.
- Latency measurements for local API probes.
- Stable, machine-readable terminal status.

## 12. Testing obligations

The generated application must be subjected to:

- Python compilation.
- Unit tests.
- Service/integration tests.
- API contract and negative tests.
- Idempotency replay and conflict tests.
- Domain invariant and state-transition tests.
- PII/secret leakage tests.
- Mock-boundary and prohibited-network scans.
- Ruff static analysis.
- MyPy type analysis.
- Runtime health/readiness/OpenAPI probes.
- Fictional create, inquiry, and replay demonstration.
- Package-hygiene and checksum verification.

## 13. Acceptance criteria

- Create and retrieve a dispute using fictional data.
- Replay the same request idempotently.
- Reject zero/negative amount and missing transaction reference.
- Expose health, readiness, OpenAPI, and local Swagger documentation.
- Produce traceable test and evidence manifests.

All test commands, outcomes, generated artifacts, limitations, and residual
risks must be recorded in the run evidence.

## 14. Failure cases

The run must fail closed when:

- Approval is absent or incorrect.
- The requirements file is missing, too small, or unreadable.
- The application ID is invalid.
- Output or evidence paths escape the isolated workspace.
- Live-payment or external-provider access is requested.
- A secret or real-person data pattern is detected.
- Generated tests, static analysis, or runtime probes fail.
- Evidence manifests do not match their files.
- A production-readiness or certification claim is attempted.

## 15. Non-goals and limitations

- No real payment processing.
- No real customer, merchant, bank, PSP, NPCI, issuer, or acquirer data.
- No automated refund, reversal, debit, credit, account restriction, or filing.
- No production deployment.
- No legal, compliance, regulatory, or certification determination.
- The current deterministic factory adapter generates a common
  production-shaped case-service architecture for each application ID.
  Scenario-specific requirements and traceability differ, but code structure
  may remain similar until separately governed domain-specific templates are
  implemented.

## 16. Official-reference boundary

Use the official-reference index at `docs/OFFICIAL_REFERENCES.md` for domain
orientation. Current obligations must be confirmed independently before any
real-world implementation or deployment.
