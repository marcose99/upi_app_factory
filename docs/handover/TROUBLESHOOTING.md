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

Start the canonical local portal:

```bash
./run_factory.sh --port 0 --no-browser
```

If startup fails, inspect `.var/upi_app_factory/logs/operator_portal.jsonl`.
Use `./stop_factory.sh --state-root .var/upi_app_factory` to clear a validated
stale PID. The launcher refuses non-loopback hosts and reports port conflicts
with a retry path.

## Validators fail

Do not bypass validators. Create or run a governed repair script, then rerun the
validator set.

## Live integration request appears

Stop. Current scope does not permit live NPCI/RBI/bank/PSP/ODR/payment rail integration.
