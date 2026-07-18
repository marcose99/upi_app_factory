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
- id: P70-FDNC-REQ-001; name: Failed debit case operator; description: Intake and review fictional failed debit/no credit cases with stable lineage and redacted case data.

# Use Cases
- id: P70-FDNC-DOM-002; name: Failed debit lifecycle; description: Model received, validated, evidence pending, investigation, decisioned, remediated, closed and rejected states with guarded transitions.

# Bounded Contexts
- id: P70-FDNC-CTX-001; name: UPI failed debit exception context; description: Owns failed debit/no credit aggregate state, policies, events and local mock evidence.

# Commands
- id: P70-FDNC-APP-003; name: Failed debit commands; description: OpenFailedDebitCase, AttachMockSwitchEvidence, AssessFailedDebit and RecordMockRefundInstruction are idempotent and concurrency guarded.

# Queries
- id: P70-FDNC-QRY-001; name: Failed debit queries; description: Query case state, work queue and hash-chained audit timeline with redacted fields.

# Events
- id: P70-FDNC-EVT-001; name: Failed debit events; description: FailedDebitCaseOpened, MockSwitchStatusRequested, CreditNotFound and RefundInstructionQueued are outbox-backed.

# Aggregates
- id: P70-FDNC-AGG-001; name: FailedDebitCase; description: Preserves immutable fictional transaction reference, amount, lifecycle state and optimistic version.

# Invariants
- id: P70-FDNC-INV-001; name: Failed debit safety invariants; description: Duplicate idempotency keys replay the original result and stale aggregate versions fail closed.

# Workflows
- id: P70-FDNC-WFL-001; name: Failed debit evidence workflow; description: Mock switch and mock core banking status are collected before remediation is recorded.

# APIs
- id: P70-FDNC-API-001; name: Failed debit local API; description: Commands and queries are exposed through local application services and mock ports only.

# Data
- id: P70-FDNC-DATA-001; name: Failed debit value objects; description: Fictional case id, transaction reference, money, redacted party handle and beneficiary credit status validate safe input.

# Security
- id: P70-FDNC-SEC-001; name: Failed debit security; description: Local fictional roles, object authorization, PII redaction and safe validation are mandatory.

# Operations
- id: P70-FDNC-OPS-001; name: Failed debit operations; description: Replay, audit-chain verification, outbox inspection and perf-smoke checks run offline.

# Evidence
- id: P70-FDNC-EVD-004; name: Failed debit evidence; description: Unit, integration, contract, negative, resilience, security, perf-smoke and replay/audit obligations are reported with residual risks.

# Dependencies
- id: P70-FDNC-DEP-001; name: Local stdlib mocks; description: Uses deterministic local files and Python standard library friendly fixtures.
