# Generated Application Regeneration Guide

The generated application is intentionally disposable.

Durable:
- factory governance
- prompts
- validators
- run logs
- generation ledgers
- audit evidence
- lifecycle artifacts
- portals

Disposable:
- `workspace/factory_generated/upi_dispute_resolution/generated_application/`

Safe reset command:

```bash
python scripts/reset_generated_application_workspace.py --run-id first_governed_generation_run_001
```

After reset, run the generation/runtime commands and validation gates.

Expected behavior:
- previous generated app is archived
- reset manifest is written
- generated_application workspace is recreated
- lifecycle evidence remains preserved
