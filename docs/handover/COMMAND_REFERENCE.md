# Command Reference

Canonical clean-clone startup:

```bash
./run_factory.sh --no-browser
./run_factory.sh --host 127.0.0.1 --port 0 --state-root .var/upi_app_factory --url-file .var/upi_app_factory/operator_url.txt --no-browser
./stop_factory.sh --state-root .var/upi_app_factory
```

Lower-level launcher:

```bash
./start_factory.sh --host 127.0.0.1 --port 8036 --state-root .var/upi_app_factory
```

The previously documented future `./factory ...` quick path is not currently
possible in this repository because `factory/` is a Python package directory and
no root executable named `factory` is created.

Current script equivalents for the historical operator shortcuts:

```bash
# ./factory doctor
scripts/validate_public_clone_readiness.py --repo . --license Apache-2.0

# ./factory generate
scripts/run_portal_requirements_driven_application_engineering.py \
  --requirements examples/requirements/01_upi_failed_debit_no_credit.md
```

Current generated application test command:

```bash
PYTHONPATH=workspace/factory_generated/upi_dispute_resolution/generated_application/app \
  python -m pytest -q workspace/factory_generated/upi_dispute_resolution/generated_application/tests
```
