# Factory Handover Runbook

> **Status:** Canonical current-state documentation
> **Purpose:** Give recipients the source-truth-first handover sequence.
> **Audience:** handover reviewers and recipients
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC/IEEE 15289:2019

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


1. Verify the exact repository revision/evidence supplied by the governed handover.
2. Follow [Quickstart](../handover/QUICKSTART.md).
3. Use `./run_factory.sh`; do not replace the recipient lock route with a development editable install.
4. Verify `/health` and `/operator-ui/`.
5. Review [Architecture](../current_state/ARCHITECTURE.md), [Security](../security/SECURITY_ARCHITECTURE_AND_THREAT_MODEL.md) and [Release Governance](../governance/RELEASE_GOVERNANCE.md).
6. Preserve evidence and escalate protected-action requests.

## Exit criteria

The handover exits successfully only when the exact governed revision is identified, recipient startup/health succeeds, required documentation/evidence is available, and no protected action or unresolved safety finding remains.

The heading **Factory Handover Runbook** is intentionally retained as the historical Phase 13C compatibility identity.
