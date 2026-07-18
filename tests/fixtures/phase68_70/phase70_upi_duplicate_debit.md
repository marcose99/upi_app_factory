---
app_id: upi_app_factory
product_name: UPI App Factory
repository_id: upi_app_factory
domain: phase70_multi_domain_application_engineering
runtime_llm_calls_default: 0
real_payment_calls: disabled
data_policy: fictional-data-only
---

# Actors
- id: P70-DD-REQ-001; name: Duplicate debit operator; description: Reviews fictional duplicate debit clusters with stable case and evidence identifiers.

# Use Cases
- id: P70-DD-DOM-002; name: Duplicate debit lifecycle; description: Model duplicate debit intake, validation, evidence, investigation, decision, remediation and closure.

# Bounded Contexts
- id: P70-DD-CTX-001; name: Duplicate debit context; description: Owns duplicate clustering, aggregate decisions, policies and replayable events.

# Commands
- id: P70-DD-APP-003; name: Duplicate debit commands; description: OpenDuplicateDebitCase, MatchDuplicateCandidate, ConfirmDuplicateDebit and QueueDuplicateDebitRemediation are concurrency guarded.

# Queries
- id: P70-DD-QRY-001; name: Duplicate debit queries; description: Query duplicate case, cluster membership and audit timeline with redaction.

# Events
- id: P70-DD-EVT-001; name: Duplicate debit events; description: DuplicateDebitCaseOpened, DuplicateCandidateMatched, DuplicateDebitConfirmed and DuplicateRemediationQueued enter the outbox.

# Aggregates
- id: P70-DD-AGG-001; name: DuplicateDebitCase; description: Preserves duplicate cluster key, immutable transaction references and aggregate version.

# Invariants
- id: P70-DD-INV-001; name: Duplicate debit invariants; description: Same idempotency key returns original result and closed clusters do not reopen.

# Workflows
- id: P70-DD-WFL-001; name: Duplicate matching workflow; description: Mock transaction ledger and deterministic matcher complete before decision.

# APIs
- id: P70-DD-API-001; name: Duplicate debit local API; description: Local command and query services expose duplicate case operations.

# Data
- id: P70-DD-DATA-001; name: Duplicate debit value objects; description: DuplicateClusterKey validates payer, payee, amount, window and mock rail fingerprint.

# Security
- id: P70-DD-SEC-001; name: Duplicate debit security; description: Object authorization and redacted audit views are mandatory.

# Operations
- id: P70-DD-OPS-001; name: Duplicate debit operations; description: Deterministic replay verifies cluster projection, audit chain and outbox contents.

# Evidence
- id: P70-DD-EVD-004; name: Duplicate debit evidence; description: All Phase 70 test categories and residual risks are reported.

# Dependencies
- id: P70-DD-DEP-001; name: Local duplicate mocks; description: Uses deterministic local transaction ledger and matcher fixtures.
