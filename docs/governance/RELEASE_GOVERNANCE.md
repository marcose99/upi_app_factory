# Release Governance

> **Status:** Canonical current-state documentation
> **Purpose:** Define exact repository quality gates and protected delivery boundaries for documentation and release candidates.
> **Audience:** maintainers, release engineers, reviewers, auditors and technical leadership
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference
- SLSA 1.2 concepts; CycloneDX/SPDX SBOM concepts without level/certification claims

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Governed CI contract

The current hosted `Governed CI` workflow contains exactly seven required jobs:

1. Governance policy
2. Public clone hygiene
3. Ruff
4. MyPy
5. Focused tests
6. Docker platform contract
7. Full regression

A green run on another revision is not transferable acceptance evidence.

## Protected actions

HD-P0-01 fixes the control plane in `MANUAL_PROTECTED_ACTIONS` mode: protected
actions are human-only, and conflicts or unknown effects resolve to `DENY`. Agents and
controllers have no authority to authorize protected actions. An approval record
is evidence for the bound human action only; it must not grant agent authority.

1. candidate/source reconstruction and local qualification;
2. governed commit + documentation-branch push + draft PR/exact-head CI;
3. exact fast-forward-only `main` delivery + post-push CI;
4. post-documentation RC requalification;
5. RC1 tag publication.

Each requires explicit authorization. Force push, release, deployment and certification claims are not implied by lower stages.

## Delivery principles

- Fail closed on identity drift.
- Preserve candidate/history/evidence.
- Main delivery is exact fast-forward only when separately authorized.
- Do not squash/rewrite an already-qualified candidate merely for cosmetic history.
- No force push as the default repair/delivery mechanism.
- Tagging occurs only after fresh post-documentation RC requalification proves zero blockers.
