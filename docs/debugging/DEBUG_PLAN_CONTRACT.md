# Debug Plan Contract

UPI App Factory debug plans use schema `upi-app-factory.debug-plan.v1`.
Supported plan kinds are `factory` and `generated_application`.

Each plan is generated from repository or generated-application source and
contains source file SHA-256 values, route inventories using `{method,path}`,
state machines with `{name,transitions}` and `{from,to}`, safe argv command
arrays, validation provenance, diagnostics, safety boundaries, rollback, and
escalation.

Plans must validate with:

```bash
python scripts/validate_debug_plan.py --plan <plan.json> --project-root .
```

Generated applications carry `docs/DEBUG_PLAN.md` and
`evidence/debug_plan.json`; both are included in generated manifests and source
downloads.
