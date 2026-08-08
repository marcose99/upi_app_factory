# Repository Governance

> **Status:** Canonical current-state documentation
> **Purpose:** Describe current repository quality gates, ownership and protected actions.
> **Audience:** maintainers, reviewers and auditors
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Required Governed CI checks

- Governance policy
- Public clone hygiene
- Ruff
- MyPy
- Focused tests
- Docker platform contract
- Full regression

## Review model

`.github/CODEOWNERS` records ownership. Self-owned review does not manufacture independence; independent approval requires a genuinely distinct authorized reviewer.

## Protected decisions

Documentation/source reconstruction, governed branch delivery/CI, `main` delivery, RC requalification, tagging, release, deployment and certification claims are separate protected boundaries. See [Release Governance](RELEASE_GOVERNANCE.md).

## Safety boundary

The accepted default remains fictional/local-first/mock-safe. Production payment processing and live provider calls are not implied.
