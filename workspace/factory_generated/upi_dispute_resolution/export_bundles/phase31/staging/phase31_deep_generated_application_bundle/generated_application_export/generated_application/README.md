# Generated UPI Dispute Resolution Application

This is a governed generated application output from UPI App Factory. It is
locally runnable for deterministic mock review.

It is a local FastAPI application for UPI/payment dispute-resolution simulation.
External ecosystem integrations are strictly mock/simulated: banks, PSPs,
NPCI/UPI rails, RBI systems, ODR systems, settlement, notifications, and
customer systems are not live integrations.

## Local Run

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application
PYTHONPATH=.. python -m uvicorn generated_application.app.interfaces.api.main:app --reload
```

Reviewer-oriented local run pack:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/start_local.sh
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/health_check.py
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/smoke_test.py
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/validate_local_run_pack.py
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/clean_local_artifacts.sh
```

See `docs/local_run_pack/README.md` for health checks, reset instructions, and
mock-only local runtime boundaries.

`generated_application.app.interfaces.api.main:app` is the current runnable API.
`generated_application.app.upi_dispute_app.main` and top-level `app/disputes`
files are generated compatibility facades for older recipient imports only.

## Local Tests

```bash
PYTHONPATH=workspace/factory_generated/upi_dispute_resolution \
  python -m pytest -q workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests
```

This generated app does not claim production readiness, regulatory compliance,
RBI approval, NPCI certification, live payment operation, or legal sufficiency.
