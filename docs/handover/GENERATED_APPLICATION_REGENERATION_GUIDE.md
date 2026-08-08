# Generated Application Regeneration Guide

> **Status:** Canonical current-state documentation
> **Purpose:** Define the current governed regeneration/reproducibility distinction.
> **Audience:** factory engineers and recipients
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC/IEEE 15289:2019

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


**Regeneration** is a factory engineering action using current requirements/planning/approval/engineering/validation contracts. **Reproduction** is a recipient action proving an already-generated source bundle can bootstrap/run independently from its own locks/contracts.

Do not confuse recipient clean-room bootstrap with factory regeneration.
