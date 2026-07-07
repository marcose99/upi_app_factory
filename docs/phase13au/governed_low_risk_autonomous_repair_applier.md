# Phase 13AU — Governed Low-Risk Autonomous Repair Applier

## Purpose

Phase 13AU proves bounded automatic self-healing for known low-risk repair classes.

The repair applier can automatically repair only explicit local sandbox targets. It records classification, target path, before/after digests, backup snapshot, rollback plan, evidence, and blocked-action checks.

## Safety boundary

Phase 13AU does not delete the real generated application.

Phase 13AU does not overwrite the real generated application.

Phase 13AU does not modify the project worktree automatically.

Phase 13AU does not call live providers.

Phase 13AU does not call external systems.

Phase 13AU does not apply factory self-modifications.

Phase 13AU does not merge, tag, or release automatically.

## Allowed repair classes in this phase

```text
REPAIR-DOC-001   documentation phrase repair
REPAIR-TYPE-001  low-risk typing annotation text repair
REPAIR-TERM-001  application engineering terminology repair
```

## Required repair evidence

```text
repair class
risk tier
target path
before digest
after digest
backup snapshot
rollback plan
evidence
blocked actions checked
sandbox acknowledged
```

## Governance improvement introduced

Phase 13AT created autonomous standards-gap phase blueprints. Phase 13AU adds the first bounded automatic self-healing mechanism: known low-risk repairs may execute automatically only in explicit sandbox targets with deterministic evidence.
