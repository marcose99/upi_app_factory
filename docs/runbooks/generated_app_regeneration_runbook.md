# Generated Application Regeneration Runbook

> **Status:** Canonical current-state documentation
> **Purpose:** Describe the governed regeneration boundary without obsolete phase-specific commands.
> **Audience:** factory engineers and reviewers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC 20000-1:2018 and SRE practices
- ISO/IEC/IEEE 15289:2019

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


Regeneration must use the current factory application-engineering path and preserve deterministic requirements/run identity, generated-app dependency ownership and validation evidence.

Do not manually edit the generated application to simulate factory capability. If regeneration changes product semantics or generation logic, treat it as an engineering change requiring its own qualification.

See [System Overview](../current_state/SYSTEM_OVERVIEW.md), [Architecture](../current_state/ARCHITECTURE.md) and [Requirements and Traceability](../requirements/REQUIREMENTS_AND_TRACEABILITY.md).

## Legacy Phase 13C compatibility contract — Generated App Regeneration Runbook

The historical contract phrase **Only the generated application workspace** refers to the bounded regeneration artifact scope used by that phase. Current regeneration remains governed by executable factory application-engineering contracts and must not modify unrelated repository state merely to satisfy a historical phrase.
