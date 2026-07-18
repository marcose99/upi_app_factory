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
- id: P70-FMT-REQ-001; name: Fraud triage operator; description: Reviews fictional fraud or mule-account triage cases with least-data access.

# Use Cases
- id: P70-FMT-DOM-002; name: Fraud triage lifecycle; description: Model fraud triage intake, validation, evidence, investigation, decision, remediation and closure.

# Bounded Contexts
- id: P70-FMT-CTX-001; name: Fraud mule triage context; description: Owns deterministic risk signals, mock graph evidence and manual-review decisions.

# Commands
- id: P70-FMT-APP-003; name: Fraud triage commands; description: OpenFraudTriageCase, AttachRiskSignals, EscalateManualReview and RecordTriageOutcome are audit chained.

# Queries
- id: P70-FMT-QRY-001; name: Fraud triage queries; description: Query triage case, triage queue and evidence ledger with redaction.

# Events
- id: P70-FMT-EVT-001; name: Fraud triage events; description: FraudTriageOpened, RiskSignalsCollected, ManualReviewRequired and TriageOutcomeRecorded are replayable.

# Aggregates
- id: P70-FMT-AGG-001; name: FraudTriageCase; description: Preserves triage signal lineage, aggregate version and manual-review outcome.

# Invariants
- id: P70-FMT-INV-001; name: Fraud triage invariants; description: Least-data views redact sensitive tokens and automated adverse action is not claimed.

# Workflows
- id: P70-FMT-WFL-001; name: Fraud triage workflow; description: Mock risk signals and mock mule graph evidence are collected before outcome.

# APIs
- id: P70-FMT-API-001; name: Fraud triage local API; description: Local command and query services expose triage operations.

# Data
- id: P70-FMT-DATA-001; name: Fraud triage value objects; description: TriageSignalSet validates bounded fictional risk signals with source lineage.

# Security
- id: P70-FMT-SEC-001; name: Fraud triage security; description: Role-scoped authorization, PII redaction and safe validation are mandatory.

# Operations
- id: P70-FMT-OPS-001; name: Fraud triage operations; description: Replay, audit chain, outbox and security evidence are produced offline.

# Evidence
- id: P70-FMT-EVD-004; name: Fraud triage evidence; description: Unit through replay/audit obligations and residual risks are reported.

# Dependencies
- id: P70-FMT-DEP-001; name: Local risk mocks; description: Uses fictional risk signal, graph and role policy fixtures.
