# Generated Application Delete/Recreate Runbook

The factory must always be able to delete and recreate the generated application.

Reset target:
- `workspace/factory_generated/upi_dispute_resolution/generated_application`

Governed reset command:
```bash
python scripts/reset_generated_application_workspace.py --run-id first_governed_generation_run_001
```

Dry-run command:
```bash
python scripts/reset_generated_application_workspace.py --run-id first_governed_generation_run_001 --dry-run
```

Rules:
- Reset may affect only the generated application workspace.
- Reset must never delete governance docs, prompts, validators, factory source, tests, run logs, lifecycle artifacts, generation-run manifests, audit portal, tags, or historical evidence.
- Default reset archives the previous generated application before deletion.
- After reset, the canonical generated application skeleton must exist.
- Each reset writes a reset manifest for audit and demo repeatability.
