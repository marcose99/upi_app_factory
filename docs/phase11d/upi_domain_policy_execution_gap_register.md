# UPI Domain Policy Execution Gap Register

This register tracks UPI policy areas that are referenced by prompts but still need executable policy artifacts.

Required executable policy candidates:
- upi_domain_policy_matrix.json
- failed_transaction_tat_rules.json
- complaint_lifecycle_state_machine.json
- unauthorized_transaction_handling_rules.json
- odr_escalation_policy.json
- pii_masking_policy.json
- regulatory_gap_register.md

Current status:
- These are not blockers for Phase 11D readiness.
- They are blockers before any claim of domain completeness.
- They must remain evidence-backed and must not claim regulatory compliance.
