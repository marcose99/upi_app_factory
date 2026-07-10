# Phase 46C — Governed Compatibility and Identity Migration Planning

Phase 46C converts Phase 46A findings and the Phase 46B rollback lessons into a deterministic, contract-first migration plan.

This phase is planning-only. It does not rename the repository, move Python namespaces, change generated applications, rewrite historical evidence, or apply display-branding changes.

The planner produces:

- a decision for every deterministic identity or path finding;
- six ordered migration waves;
- an additive compatibility-alias registry;
- explicit human gates for physical rename, cutover, and compatibility removal;
- a digest-protected migration plan;
- a checksummed review bundle.

Key rule:

> Compatibility is added before migration, and removed only after evidence-backed deprecation plus explicit human approval.

Commands:

```bash
./bin/upi-app-factory transform plan-identity-migration
./bin/upi-app-factory transform migration-plan-status
./bin/upi-app-factory transform verify-migration-plan --run-id <run-id>
```

Normal Phase 46C planning performs zero repository mutations and zero LLM calls.

