# Phase 70 Portfolio Depth Matrix

This matrix records the deterministic evidence expected for each Phase 70 capability profile. It is a local engineering-evidence contract, not an official certification claim and not a production-readiness claim.

| Profile | Requirements Lineage | Domain Model | Application Surface | Safety and Evidence |
| --- | --- | --- | --- | --- |
| `upi_failed_debit_no_credit` | `P70-FDNC-REQ-001`, `P70-FDNC-DOM-002`, `P70-FDNC-APP-003`, `P70-FDNC-EVD-004` | failed debit lifecycle, mock switch credit status, refund instruction events | failed debit commands, queries, mock UPI switch/core banking/notification ports | idempotency, optimistic versioning, redaction, replay/audit, residual risk report |
| `upi_reversal_refund_tracking` | `P70-RR-REQ-001`, `P70-RR-DOM-002`, `P70-RR-APP-003`, `P70-RR-EVD-004` | refund status lifecycle, aging buckets, reversal suppression | refund commands, status queries, mock refund rail/ledger/outbox ports | duplicate status collapse, customer-safe status, replay projection evidence |
| `upi_duplicate_debit` | `P70-DD-REQ-001`, `P70-DD-DOM-002`, `P70-DD-APP-003`, `P70-DD-EVD-004` | duplicate clustering, immutable transaction references, remediation events | duplicate commands, cluster queries, mock ledger/matcher/audit ports | cluster replay checksum, stale-write rejection, redacted audit views |
| `merchant_qr_acquirer_dispute` | `P70-MQA-REQ-001`, `P70-MQA-DOM-002`, `P70-MQA-APP-003`, `P70-MQA-EVD-004` | QR payload validation, acquirer evidence, settlement mock reconciliation | merchant QR commands, acquirer queries, mock acquirer/registry/QR validator ports | unsafe QR rejection, acquirer evidence deadline, outbox evidence |
| `fraud_mule_account_triage` | `P70-FMT-REQ-001`, `P70-FMT-DOM-002`, `P70-FMT-APP-003`, `P70-FMT-EVD-004` | risk signal lineage, manual review escalation, triage outcome events | triage commands, queue queries, mock risk/graph/access-policy ports | least-data access, no automated adverse-action claim, security evidence |
| `card_authorization_chargeback` | `P70-CAC-REQ-001`, `P70-CAC-DOM-002`, `P70-CAC-APP-003`, `P70-CAC-EVD-004` | masked card reference, mock auth trace, chargeback representment | card exception commands, chargeback queries, mock card/issuer/evidence ports | PAN-safe validation, masked audit trail, replay/audit evidence |

All profiles carry eight test obligation categories: unit, integration, contract, negative, resilience, security, performance-smoke and replay/audit.
