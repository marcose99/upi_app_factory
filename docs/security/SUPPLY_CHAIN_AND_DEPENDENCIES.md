# Supply Chain and Dependencies

> **Status:** Canonical current-state documentation
> **Purpose:** Document exact dependency closure, generated-application reproducibility, vulnerability/SBOM evidence and provenance boundaries.
> **Audience:** developers, security reviewers, release engineers, recipients and auditors
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference
- SLSA 1.2 concepts; CycloneDX/SPDX SBOM concepts without level/certification claims

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Factory recipient dependency model

`run_factory.sh` incorporates `requirements/bootstrap-lock.txt`, `requirements-recipient.txt`, `requirements/recipient-lock.txt` and `pyproject.toml` into recipient environment identity. Installed distributions are checked against exact versions; unexpected unlocked distributions are rejected apart from the permitted first-party package; `pip check` must pass.

## Generated application dependency ownership

The authoritative generated application owns its clean-room bootstrap/runtime-test locks, dependency contract and fail-closed validator. Recipient reproducibility must not borrow the factory repository's existing `.venv`.

## Vulnerability and SBOM evidence

Qualification supports known-vulnerability audit evidence and CycloneDX SBOM generation. First-party local source is separated from third-party package-index lookup.

## Provenance posture

Exact source/tree/evidence identities and reproducible handover artifacts are preserved. SLSA concepts are used as a provenance reference, but **no SLSA level is claimed** unless separately satisfied and governed.

## Runtime secret boundary

Dependency reproducibility does not imply secret inheritance: generated runtime processes receive a sanitized environment and accepted mock/default-off safety flags.
