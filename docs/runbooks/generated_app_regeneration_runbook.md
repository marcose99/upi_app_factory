# Generated App Regeneration Runbook

## Objective

Delete and recreate the generated app safely while preserving factory evidence.

## Command

```bash
python scripts/reset_generated_application_workspace.py --run-id first_governed_generation_run_001
```

## Verify

```bash
python scripts/validate_phase13a_generated_application_regeneration.py
```

## Then

Run generation/runtime commands and validation gates.

## Safety

Only the generated application workspace may be reset. Governance, prompts, validators,
lifecycle artifacts, run logs, portals, and ledgers must remain preserved.
