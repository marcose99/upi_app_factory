# Phase 14K — Governed Autonomous Phase Execution Loop

## Purpose

Phase 14K turns the Phase 14J orchestrator into a practical governed autonomous execution loop.

The loop can plan the next phase, create candidate artifacts, run validation gates, diagnose failures, apply only policy-approved low-risk repairs, rerun gates, emit evidence, and stop at human approval.

## Execution loop stages

```text
load_orchestrator_boundary
select_candidate_phase
generate_candidate_phase_plan
generate_candidate_artifact_manifest
run_validation_gate_plan
classify_failures
apply_allowed_low_risk_repairs
rerun_validation_gate_plan
emit_execution_evidence
stop_at_human_approval_gate
```

## Candidate next phases

```text
14L_OPERATOR_PORTAL_AUTONOMOUS_CERTIFICATION_DASHBOARD_INTEGRATION
14M_GENERATED_APPLICATION_MATURITY_SWEEP
14N_V1_RELEASE_CANDIDATE_REPLAY_GATE
```

## Human approval boundary

The loop must stop before:

```text
promotion
merge to main
tag creation
release declaration
destructive generated-application mutation
live provider calls
external system calls
official certification claims
official certification decisions
```

## Certification boundary

The generated application is certification-ready, not certified.

The factory does not self-certify generated applications.

The factory does not grant official certification.

Final certification remains with authorized certifying authorities.

## Governance improvement introduced

Phase 14J defined the orchestrator. Phase 14K provides the execution loop that can drive the remaining phases as governed autonomous self-engineering while keeping all hard boundaries intact.
