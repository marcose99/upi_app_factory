# Generated Application Handover

Authoritative path: `workspace/factory_generated/upi_dispute_resolution/generated_application`.

A recipient should be able to copy/extract the source bundle and run:

```bash
./scripts/bootstrap_cleanroom.sh
.venv/bin/python scripts/validate_dependency_contract.py
.venv/bin/python -m pytest -q app/tests
./scripts/start_local.sh
```

Required handover artifacts are exact bootstrap/runtime-test locks, dependency contract, bootstrap/validator, tests and runtime health/smoke scripts. Tampered/non-exact/incomplete dependency state must fail closed.

The handover is a source bundle; wheel packaging and production deployment are not claimed.
