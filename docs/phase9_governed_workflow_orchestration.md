# Phase 9: Governed Workflow Orchestration and Checkpointing

Phase 9 adds a deterministic workflow layer above the Phase 8 multi-agent
simulation.

The purpose is not to introduce autonomous LLM execution. The purpose is to
prove that the factory can execute a governed lifecycle plan, record checkpoints,
represent paused workflow state, and validate workflow evidence.

## Workspace

Workflow runs are written under:

```text
workspace/workflow_runs/<run_id>/
```

Each run emits:

```text
workflow_run_manifest.json
workflow_execution_plan.json
workflow_state.json
workflow_checkpoints.jsonl
workflow_audit_events.jsonl
workflow_validation_report.json
workflow_resume_report.json
```

## Workflow steps

The Phase 9 deterministic workflow has seven steps:

1. Intake governed requirement context.
2. Review domain assumptions and mock boundaries.
3. Prepare architecture and planning handoff.
4. Validate implementation and test readiness.
5. Perform security and governance review gate.
6. Prepare release and operations evidence.
7. Confirm traceability and validation closure.

## Human-review gate

Phase 9 records a human-review gate as evidence, but it does not implement an
interactive approval console. The goal is to make the gate visible and auditable
before adding real approval workflows later.

## Resume behavior

Phase 9 can create a paused workflow run with `--stop-after-step`. It records:

- completed steps,
- blocked steps,
- resume candidate step,
- checkpoint evidence.

True replay/resume execution is intentionally left for a future phase.

## Honesty and mock boundaries

Phase 9 preserves the project honesty labels:

- `MISSING_OFFICIAL_SOURCE`
- `SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL`
- `MOCK_BOUNDARY`
- `SYNTHETIC_DATA`

The workflow must not claim official UPI/NPCI/RBI behavior without approved
official evidence.

## Commands

```bash
make run-governed-workflow
make validate-workflow-run
```

Manual example:

```bash
python scripts/run_governed_workflow.py --run-id manual_workflow_review --force
python scripts/validate_workflow_run.py --run-dir workspace/workflow_runs/manual_workflow_review
```

Paused workflow example:

```bash
python scripts/run_governed_workflow.py \
  --run-id manual_paused_workflow_review \
  --force \
  --stop-after-step WF-P9-003
```

## Current limitation

Phase 9 is a deterministic workflow orchestration baseline. Later phases can add
true resume execution, richer workflow branching, interactive approvals, and
integration with real agent/tool execution.
