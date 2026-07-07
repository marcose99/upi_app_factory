# Phase 16: Self-contained handoff replay hardening

## Purpose
Phase 16 turns the Phase 15 fresh-clone finding into governed self-evolution. Phase 15 proved scoped tagged-v1 replay, but also recorded that full fresh-clone pytest had legacy dependencies on untracked workspace evidence and clone-local virtualenv assumptions. Phase 16 hardens the repository so future handoff tags can be replayed from a fresh clone without depending on hidden local state.

## Scope
- Materialize and commit legacy workspace evidence required by historical validators and tests.
- Repair test portability that assumes `.venv/bin/python3` exists inside a fresh clone.
- Preserve the certification-ready-not-certified boundary.
- Run current-repository full regression from a clean committed tree.
- Run full fresh-clone replay against the Phase 16 candidate commit.
- Record replay evidence without claiming official certification.

## Governance boundaries
The factory may autonomously harden documentation, policy, tests, validators, and evidence packaging where the change is low-risk and reproducibility-improving. It must not perform official certification, live provider calls, destructive production operations, release promotion, or risky generated-application business changes without human approval.

## Certification boundary
This phase improves evidence readiness only. The generated application remains certification-ready-not-certified. Official certification still requires certifying authority review, independent verification, formal audit or compliance assessment, regulatory or industry standard assessment, production validation where required, security/privacy/resilience/operational review, and an official certification decision.

## Phase 16 v3 replay repair

The governed self-contained fresh-clone replay exposed one remaining mirrored-evidence gap: the Phase 13C handover deployment documentation manifest existed in the generation-run evidence path but was absent from the lifecycle-artifact mirror path required by the legacy Phase 13C validator. Phase 16 v3 performs a safe evidence-packaging repair by mirroring the already generated manifest into lifecycle artifacts. This does not claim certification, does not mutate external systems, and does not alter generated application business logic.

## Phase 16 v4 replay sequencing repair

Phase 16 v4 replay sequencing repair: the Phase 13C handover manifest is mirrored before the candidate fresh-clone replay; the Phase 16 validator is intentionally run only after the replay evidence is regenerated with PASS status. This is evidence packaging only and does not alter generated application business logic.

## Phase 16 v5 force-stage manifest repair

The self-contained fresh-clone replay exposed that the Phase 13C handover deployment documentation manifest must be present in both the generation-run evidence path and the lifecycle artifact mirror path. The factory therefore performs a governed safe evidence-packaging repair by force-staging `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13c/handover_deployment_documentation_manifest.json` before candidate replay. This is an evidence packaging repair only; it does not change generated application business logic and does not claim certification.
