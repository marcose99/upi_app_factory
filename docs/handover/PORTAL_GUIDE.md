# Operator Portal Guide

> **Status:** Canonical current-state documentation
> **Purpose:** Describe current operator portal surfaces and guarded mutation model.
> **Audience:** operators, recipients and reviewers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC 20000-1:2018 and SRE practices

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Access

Start through `./run_factory.sh` and use the verified `/operator-ui/` route after health succeeds.

## Functional areas

The portal exposes local-only health, requirements intake, planning/approval, application engineering, validation, evidence/download, portfolio/runtime, scenario/lifecycle and read-only audit/evidence workflows.

Mutation controls use in-flight guards to prevent duplicate/conflicting actions while preserving unrelated read-only access.

## Charts and visuals

Charts and visuals summarize local evidence/runtime state where those surfaces are available; they do not replace machine-readable evidence.

## Audit and self-correction

Use audit/self-correction evidence where those portal surfaces are available. Bounded self-correction must stop for semantic/security/protected-boundary changes.

See [Operator Portal Control Contract](../operator_portal/control_contract.md).
