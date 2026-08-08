# Release Package Specification

> **Status:** Canonical current-state documentation
> **Purpose:** Define recipient package integrity and non-claims.
> **Audience:** release engineers, recipients and auditors
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- SLSA 1.2 concepts; CycloneDX/SPDX SBOM concepts without level/certification claims

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


A governed handover package identifies exact source/tree/evidence, required files/checksums, recipient commands, dependency closure, generated application artifacts and explicit truth/non-claim boundaries.

Pinned checksum/manifest files must be reconciled whenever a required release file changes. A handover package does not by itself constitute a GitHub release, deployment or certification.
