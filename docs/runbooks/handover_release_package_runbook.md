# Handover Release Package Runbook

> **Status:** Canonical current-state documentation
> **Purpose:** Describe governed local handover packaging and integrity verification.
> **Audience:** release engineers, recipients and reviewers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- SLSA 1.2 concepts; CycloneDX/SPDX SBOM concepts without level/certification claims

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


A handover package must preserve exact source/evidence identities, required release-file checksums, recipient commands and explicit truth boundaries. Documentation changes that alter a pinned release-file hash must reconcile the dependent manifest/checksum evidence deterministically before qualification.

See [Release Governance](../governance/RELEASE_GOVERNANCE.md) and [Supply Chain and Dependencies](../security/SUPPLY_CHAIN_AND_DEPENDENCIES.md).
