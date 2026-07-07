# Phase 13AY — Operator Portal Evidence and Governance Dashboards

## Purpose

Phase 13AY expands the local Factory Operator Portal from a basic status page and guided intake preview into a read-only governance dashboard surface.

The portal now has dashboard panels for evidence/audit, standards controls, self-healing, agentic threats, requirement intake, handover replay, and generated application status.

## Safety boundary

Phase 13AY is read-only.

Phase 13AY does not delete the real generated application.

Phase 13AY does not overwrite the real generated application.

Phase 13AY does not write requirement packages from the UI.

Phase 13AY does not run application engineering from the UI.

Phase 13AY does not execute arbitrary shell commands from the UI.

Phase 13AY does not call live providers.

Phase 13AY does not call external systems.

Phase 13AY does not apply factory self-modifications.

Phase 13AY does not merge, tag, or release automatically.

## Dashboard routes

```text
/dashboards
/dashboards/evidence
/dashboards/standards
/dashboards/self-healing
/dashboards/threats
/dashboards/handover
/dashboards/generated-app
/api/dashboards
```

## Governance improvement introduced

Phase 13AX added guided requirement-intake preview. Phase 13AY makes the portal significantly more usable for operators, reviewers, capstone evaluation, audit demonstration, and handover review by surfacing evidence and governance state in one browser-based place.
