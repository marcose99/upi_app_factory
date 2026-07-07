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
