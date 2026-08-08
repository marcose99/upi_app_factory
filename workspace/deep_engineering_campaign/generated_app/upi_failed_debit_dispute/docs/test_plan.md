# Test Plan

## Scope

This application engineering output proves deterministic failed-debit lifecycle behavior for `upi_failed_debit_dispute` without live providers, external databases, or runtime LLM calls.

## Required commands

1. `python -m pytest -q tests/test_service.py`
2. `python -m pytest -q tests/test_api_contract.py`
3. `python -m pytest -q`

## Coverage expectations

- Lifecycle states: `received`, `validated`, `evidence_pending`, `investigation`, `resolution_proposed`, `resolved`, `rejected`, `closed`
- API contract: health, readiness, metrics, create/list/get dispute, evidence, investigation, resolution, closure, timeline, audit
- Persistence: SQLite migration inventory and deterministic local startup
- Safety boundaries: idempotency, fictional-only data posture, no live-provider dependency, no certification/deployment claim

## Evidence outputs

- `evidence/requirements_trace.json`
- `evidence/generation_manifest.json`
- `openapi/openapi.json`
- `docs/operations_runbook.md`
