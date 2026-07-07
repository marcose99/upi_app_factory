# Workflow State Machine

Initial:
- failed/duplicate/wrong-credit disputes -> validation_pending
- unauthorized transaction -> evidence_pending

Mock outcomes:
- refund_eligible -> refund_initiated
- more_evidence_required -> customer_action_required
- escalate_to_odr -> escalated_to_odr
- reject -> rejected
