# Command Reference

Future unified CLI target:

```bash
./factory doctor
./factory bootstrap
./factory reset-generated-app
./factory generate
./factory validate
./factory audit
./factory portal
./factory package-handover
```

Current script equivalents:

```bash
python scripts/reset_generated_application_workspace.py --run-id first_governed_generation_run_001
python scripts/run_phase13c_agent_runtime_dry_run.py
python scripts/generate_phase13c_agent_runtime_portal.py
python scripts/run_phase13c_self_correction_dry_run.py
python scripts/generate_phase13c_self_correction_portal.py
python scripts/validate_phase13c_agent_runtime_foundation.py
python scripts/validate_phase13c_self_correction_governance.py
python scripts/validate_phase13b_generated_application.py
python scripts/validate_phase13b_progress_portal_observability.py
python -m pytest -q
```

Current generated application test command:

```bash
PYTHONPATH=workspace/factory_generated/upi_dispute_resolution/generated_application/app \
  python -m pytest -q workspace/factory_generated/upi_dispute_resolution/generated_application/tests
```
