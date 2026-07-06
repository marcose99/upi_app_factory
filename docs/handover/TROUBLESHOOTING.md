# Troubleshooting Guide

## Python import errors

Check `PYTHONPATH`:

```bash
export PYTHONPATH="$PWD/src:$PWD/workspace/factory_generated/upi_dispute_resolution/generated_application/app"
```

## Generated app tests fail

Run:

```bash
PYTHONPATH=workspace/factory_generated/upi_dispute_resolution/generated_application/app \
  python -m pytest -q workspace/factory_generated/upi_dispute_resolution/generated_application/tests
```

Then inspect the failure and run the governed self-correction flow.

## Portal missing

Regenerate portals:

```bash
python scripts/generate_phase13b_progress_portal.py
python scripts/generate_phase13c_agent_runtime_portal.py
python scripts/generate_phase13c_self_correction_portal.py
```

## Validators fail

Do not bypass validators. Create or run a governed repair script, then rerun the
validator set.

## Live integration request appears

Stop. Current scope does not permit live NPCI/RBI/bank/PSP/ODR/payment rail integration.
