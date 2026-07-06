# Handover Validation Runbook

## Required gates

```bash
python scripts/validate_phase13c_agent_runtime_foundation.py
python scripts/validate_phase13c_self_correction_governance.py
python scripts/validate_phase13b_generated_application.py
python scripts/validate_phase13b_progress_portal_observability.py
python scripts/validate_phase13a_generated_application_regeneration.py
python scripts/validate_phase13a_first_governed_generation_run.py
python scripts/validate_phase12b_operations_remediation_loop.py
python scripts/validate_phase12a_independent_audit_foundation.py
python -m ruff check .
python -m mypy src
python -m pytest -q
```

## Required result

- all gates pass
- no untriaged warnings/errors
- portals generated
- generated app tests pass
