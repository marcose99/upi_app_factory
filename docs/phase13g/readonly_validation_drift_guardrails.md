# Phase 13G: Read-only Validation Drift Guardrails

Phase 13G closes the workspace-drift issue discovered after Phase 13F finalization.

## Goal

Validation commands must behave as read-only gates. If an older validator still rewrites generated evidence, Phase 13G detects that drift, restores it, and reports it.

## Truth boundary

This phase does not claim that every old validator has been rewritten to be intrinsically read-only. It adds a guardrail layer around known legacy mutation points and fails on unexpected generated workspace drift.

## Operator commands

```bash
python3 scripts/run_phase13g_readonly_validation_audit.py
python3 scripts/generate_phase13g_readonly_validation_portal.py
python3 scripts/validate_phase13g_readonly_validation_guardrails.py
pytest -q tests/test_phase13g_readonly_validation_guardrails.py
```

## Evidence

- `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13g/readonly_validation_audit.json`
- `workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_readonly_validation_drift_guardrails_portal.html`

## Legacy drift currently guarded

- `workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_operator_handover_closure_portal.html`
- `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13f/operator_handover_audit.json`
