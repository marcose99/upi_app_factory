# Phase 14J — Governed Autonomous Self-Engineering Orchestrator

## Purpose

Phase 14J introduces the mechanism that lets the remaining phases run as governed autonomous self-engineering, self-healing, and self-evolution.

This is not uncontrolled autonomy.

The factory autonomously engineers, validates, repairs, and evolves only inside governed boundaries.

Human approval remains required for promotion, merge, tag, release, destructive generated-application changes, live/external calls, and certification claims.

## Allowed autonomous work

```text
read_phase_state
plan_next_phase
write_candidate_artifacts
run_policy_validators
run_targeted_tests
run_ruff
run_mypy
run_full_pytest
diagnose_failures
apply_policy_allowed_low_risk_repairs
rerun_gates
emit_evidence
stop_at_human_approval_gate
```

## Blocked or human-gated work

```text
merge_to_main_without_human_approval
create_tag_without_human_approval
release_without_human_approval
claim_official_certification
grant_certification
delete_real_generated_application
overwrite_real_generated_application_without_approval
execute_arbitrary_shell
call_live_provider
call_external_system
bypass_evidence_capture
bypass_validation_gates
```

## Certification boundary

The generated application is certification-ready, not certified.

The factory does not self-certify generated applications.

The factory does not grant official certification.

Final certification remains with authorized certifying authorities.

## What sits between generated application and certification

```text
Generated application
  ↓
Certification-ready evidence pack
  ↓
Fresh-recipient replay
  ↓
Certifying authority review workspace
  ↓
Authority findings register and remediation loop
  ↓
Certification authority submission dossier
  ↓
Certification readiness dashboard/index
  ↓
Governed autonomous self-engineering evidence
  ↓
Certifying authority review
  ↓
Independent verification
  ↓
Formal audit or compliance assessment
  ↓
Regulatory or industry-standard assessment
  ↓
Production-environment validation where required
  ↓
Security, privacy, resilience, and operational review
  ↓
Official certification decision
```

## Governance improvement introduced

Phase 14I made the certification readiness evidence inspectable. Phase 14J adds the governed autonomous self-engineering orchestrator so the factory can continue evolving itself while stopping at hard human and certification boundaries.
