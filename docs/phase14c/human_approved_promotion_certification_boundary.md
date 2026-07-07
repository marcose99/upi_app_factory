# Phase 14C — Human-Approved Promotion Gate and Certification-Ready Evidence Boundary

## Purpose

Phase 14C makes the factory's certification position explicit.

Generated applications should be engineered very close to certification standards, but one level below formal certification so certifying authorities can independently verify and certify.

## Certification boundary

```text
Generated application
  ↓
Certification-ready evidence pack
  ↓
Independent certifying authority review
  ↓
Formal audit / compliance verification
  ↓
Regulatory or industry-standard assessment
  ↓
Production-environment validation where required
  ↓
Security, privacy, resilience, and operational review
  ↓
Official certification decision by the authorized authority
```

## Required wording

The factory generates applications with certification-ready engineering discipline and evidence.

The factory does not self-certify generated applications.

The generated application is certification-ready, not certified.

Final certification remains with authorized certifying authorities.

## Promotion boundary

Phase 14C creates a human-approved promotion gate.

Phase 14C does not automatically promote sandbox output to the real worktree.

Phase 14C does not delete the real generated application.

Phase 14C does not overwrite the real generated application without approval.

Phase 14C does not execute arbitrary shell commands.

Phase 14C does not call live providers.

Phase 14C does not call external systems.

Phase 14C does not merge, tag, or release automatically.

## Evidence expected for certification authority review

```text
requirement_traceability
architecture_and_design_evidence
policy_decision_records
sandbox_generation_evidence
local_validation_reports
security_and_governance_validation_reports
mock_boundary_evidence
rollback_and_replay_evidence
handover_evidence
known_limitations_and_certification_boundary_statement
```

## Governance improvement introduced

Phase 14B produced sandbox-only generation and validation evidence. Phase 14C adds the official certification boundary and human-approved promotion gate so the factory can qualify generated applications for independent certification review without claiming that certification itself has been granted.
