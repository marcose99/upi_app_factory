# Phase 13AX — Guided Requirement Intake UI Foundation

## Purpose

Phase 13AX adds the guided requirement intake UI foundation to the local Factory Operator Portal.

The portal can now collect requirement details and produce a deterministic preview of a governed requirement package.

## Safety boundary

Phase 13AX is preview-only.

Phase 13AX does not delete the real generated application.

Phase 13AX does not overwrite the real generated application.

Phase 13AX does not write requirement packages from the UI.

Phase 13AX does not run application engineering from the UI.

Phase 13AX does not execute arbitrary shell commands from the UI.

Phase 13AX does not call live providers.

Phase 13AX does not call external systems.

Phase 13AX does not apply factory self-modifications.

Phase 13AX does not merge, tag, or release automatically.

## Guided intake fields

```text
business_domain
application_name
capabilities
regulatory_constraints
mock_ecosystem
data_sensitivity
llm_mode
approval_mode
```

## Preview sections

```text
normalized_requirement
risk_classification
governance_controls
mock_boundary
evidence_plan
blocked_actions
```

## Portal routes

```text
GET  /requirements
POST /api/requirements/preview
```

## Governance improvement introduced

Phase 13AW made the factory presentable through a read-only local portal. Phase 13AX starts turning that portal into a guided operator experience by adding requirement intake preview while preserving strict non-destructive governance.
