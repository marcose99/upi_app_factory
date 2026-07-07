# Phase 13L Dispute Case Intake Slice

This generated component is a local runnable UPI dispute-resolution application slice. It owns primary application logic for dispute case intake, validation,
case creation, and local retrieval.

External ecosystem boundaries are deliberately mock/simulated only. Bank,
NPCI-style, RBI-style, payment rail, and upstream/downstream interfaces are not
real integrations in this slice.

The generated Python package uses a phase-specific package name,
`phase13l_dispute_case_intake_app`, to avoid collision with the factory repo's
existing top-level `app` package.

## Run locally

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application/phase13l_dispute_case_intake
python3 scripts/run_smoke.py
PYTHONPATH=. python3 -m pytest -q checks/dispute_case_intake_checks.py
```
