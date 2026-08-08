# Handover Documentation

> **Status:** Canonical current-state documentation
> **Purpose:** Provide recipient-oriented navigation to canonical current documents.
> **Audience:** recipients and reviewers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC/IEEE 15289:2019

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


Start with [Quickstart](QUICKSTART.md), then:

- [Command Reference](COMMAND_REFERENCE.md)
- [Factory Architecture](FACTORY_ARCHITECTURE.md)
- [Generated Application Handover](GENERATED_APPLICATION_HANDOVER.md)
- [Portal Guide](PORTAL_GUIDE.md)
- [Environment Specification](ENVIRONMENT_SPEC.md)
- [Release Package Specification](RELEASE_PACKAGE_SPEC.md)
- [Canonical Documentation Index](../DOCUMENTATION_INDEX.md)

Historical phase documents remain provenance and must not be used as current operating instructions when they conflict with canonical current documents.

## Legacy Phase 13C compatibility contract

The historical Phase 13C validator identifies this handover family with the phrases **Factory Handover Guide**, **Truth boundary**, **Primary generated application**, and **External ecosystem**. They are retained here solely as a stable compatibility vocabulary.

- **Truth boundary:** executable source/tests/runtime contracts and governed evidence at the checked-out revision outrank historical prose.
- **Primary generated application:** `upi_dispute_resolution`.
- **External ecosystem:** payment/provider systems remain mocked or default-off in accepted local operation.
