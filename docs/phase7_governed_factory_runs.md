# Phase 7 — Governed Factory Runs

Phase 7 upgrades the project from deterministic regeneration into governed factory-run evidence.
It does **not** claim full autonomous LLM execution yet. It introduces deterministic role-agent evidence so every run can be audited, replayed, and validated.

## What Phase 7 adds

Each run writes an isolated workspace under:

```text
workspace/runs/<run_id>/
```

Required run artifacts:

```text
factory_run_manifest.json
 task_manifest.json
 agent_outputs.jsonl
 artifact_manifest.json
 validation_report.json
 known_limitations.md
 release_readiness_report.md
 audit_events.jsonl
 generated/
```

## Commands

Create a governed factory run:

```bash
RUN_ID=manual_factory_run python scripts/run_governed_factory_run.py --force
```

Validate the latest run:

```bash
python scripts/validate_factory_run_manifest.py --latest
```

Or validate a specific run:

```bash
python scripts/validate_factory_run_manifest.py --run-dir workspace/runs/manual_factory_run
```

Make targets:

```bash
make run-governed-factory-run
make validate-factory-run
```

## Traceability rule

Every generated artifact must have all of the following:

- `requirement_ids`
- `task_ids`
- `policy_ids`
- `evidence_refs`
- `sha256`
- `size_bytes`

The validator fails the run if any generated artifact lacks these links.

## Honesty labels preserved

- `MISSING_OFFICIAL_SOURCE`
- `SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL`
- `MOCK_BOUNDARY`
- `SYNTHETIC_DATA`

## Mock boundaries preserved

- `mock_upi_switch`
- `mock_core_banking`
- `mock_customer_notification`
- `mock_dispute_evidence_store`
