# Workflow State Machine

States:
- `received`
- `validated`
- `investigating`
- `awaiting_evidence`
- `awaiting_human_review`
- `decision_recorded`
- `resolved`
- `closed`
- `quarantined`

Required transitions:
- `received -> validated`
- `validated -> investigating`
- `investigating -> awaiting_evidence`
- `investigating -> awaiting_human_review`
- `investigating -> decision_recorded`
- `awaiting_evidence -> investigating`
- `awaiting_evidence -> awaiting_human_review`
- `awaiting_human_review -> decision_recorded`
- `decision_recorded -> resolved`
- `resolved -> closed`
- any non-closed state may transition to `quarantined` on integrity or policy failure

Closure guards:
- a case cannot close without a recorded disposition
- a human-review-required case cannot close without an approved review decision
- a case cannot close until audit integrity verification has passed

Segregation and boundary guards:
- supervisor approval rejects same-actor self-approval when segregation-of-duties applies
- `quarantined` is terminal in the local generated runtime
- the runtime is mock-only and does not execute payment actions
