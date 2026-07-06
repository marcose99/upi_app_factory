# Recipient Operator Runbook

## Daily/local operation

```bash
git status
python scripts/validate_phase13c_agent_runtime_foundation.py
python scripts/validate_phase13c_self_correction_governance.py
python -m pytest -q
```

## Regeneration

```bash
python scripts/reset_generated_application_workspace.py --run-id first_governed_generation_run_001
python scripts/run_phase13c_agent_runtime_dry_run.py
python scripts/generate_phase13c_agent_runtime_portal.py
```

## Inspect portals

Open the HTML files in `workspace/factory_generated/upi_dispute_resolution/audit_portal/`.

## Escalation

Escalate if:
- blocked self-correction category appears
- live integration request appears
- real customer data appears
- regulatory/certification claim appears
- dependency installation is required
- release/tag/push is required
