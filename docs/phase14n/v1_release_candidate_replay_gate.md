# Phase 14N — v1.0 Release-Candidate Replay Gate

## Purpose

Phase 14N defines the v1.0 release-candidate replay gate.

It proves that a recipient can replay the factory handover path, validate the generated application, inspect operator-facing certification readiness, and review the evidence chain.

This phase does not declare the final release.

This phase does not grant certification.

The generated application remains certification-ready, not certified.

Final certification remains with authorized certifying authorities.

## Replay gate steps

```text
fresh_clone_or_clean_checkout
python_310_environment_check
dependency_installation_check
factory_validation_gates
generated_application_tests
operator_portal_start_check
certification_readiness_dashboard_check
evidence_artifact_inventory_check
handover_runbook_check
human_release_candidate_approval_gate
```

## Human approval boundary

Human approval is required before release-candidate declaration, merge, tag, release, promotion, destructive generated-app mutation, live provider calls, external system calls, or certification claims.

## Safety boundary

Phase 14N does not release.

Phase 14N does not certify.

Phase 14N does not claim official certification.

Phase 14N does not delete or overwrite the generated application.

Phase 14N does not call live providers.

Phase 14N does not call external systems.

## Governance improvement introduced

Phase 14M checked generated application maturity. Phase 14N adds a replayable v1.0 release-candidate gate so the factory can approach v1.0 with reproducible handover evidence.
