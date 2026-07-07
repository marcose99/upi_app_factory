# Architecture, HLD, and LLD Quality Gate

Mandatory design chain:
requirements -> domain model -> architecture -> HLD -> LLD -> API contracts -> data model -> workflow/state machine -> security design -> observability design -> test strategy -> implementation plan.

Required artifacts:
- architecture_decision_records/
- hld.md
- lld.md
- api_contracts/openapi.yaml
- domain_model.md
- data_model.md
- workflow_state_machine.md
- error_handling_design.md
- security_design.md
- observability_design.md
- test_strategy.md

Quality rules:
- all design decisions must trace to requirements,
- real primary UPI application boundary must be preserved,
- external ecosystem must remain mock/simulated,
- no false production/compliance/certification claims,
- every high-risk decision must map to evidence and tests.
