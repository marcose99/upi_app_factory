# Generated UPI Dispute Resolution Application

This is the first governed generated application output from UPI App Factory.

It is a real, locally runnable FastAPI application for UPI/payment dispute-resolution
simulation. The primary application is implemented as local code. External ecosystem
integrations are strictly mock/simulated: banks, PSPs, NPCI/UPI rails, RBI systems,
ODR systems, settlement, notifications, and customer systems are not live integrations.

## Local run

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application
PYTHONPATH=app python -m uvicorn upi_dispute_app.main:app --reload
```

Phase 42 adds a reviewer-oriented local run pack:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/start_local.sh
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/smoke_test.py
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/validate_local_run_pack.py
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/clean_local_artifacts.sh
```

See `docs/local_run_pack/README.md` for health checks, reset instructions, and
mock-only local runtime boundaries.

## Local tests

```bash
PYTHONPATH=workspace/factory_generated/upi_dispute_resolution/generated_application/app \
  python -m pytest -q workspace/factory_generated/upi_dispute_resolution/generated_application/tests
```

This generated app does not claim production readiness, regulatory compliance,
RBI approval, NPCI certification, live payment capability, or legal sufficiency.
