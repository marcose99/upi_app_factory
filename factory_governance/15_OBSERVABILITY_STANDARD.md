# 15 — Observability Standard

Status: FINAL BASELINE v1.0

## 1. Objective

Every serious factory run and generated application must be traceable, diagnosable, auditable, and searchable.

## 2. Required signals

- Structured logs
- Metrics
- Traces
- Audit events
- Validation reports
- Artifact manifests
- Policy decision logs
- Tool call logs
- Approval records
- Health/readiness checks

## 3. Required IDs

Use these identifiers consistently:

- `run_id`
- `task_id`
- `agent_id`
- `trace_id`
- `span_id`
- `correlation_id`
- `artifact_id`
- `requirement_id`
- `policy_id`
- `validation_id`
- `approval_id`
- `debug_case_id`
- `error_code`

## 4. Structured log minimum fields

```json
{
  "timestamp_utc": "...",
  "level": "INFO",
  "message": "...",
  "run_id": "...",
  "task_id": "...",
  "agent_id": "...",
  "trace_id": "...",
  "correlation_id": "...",
  "event_type": "...",
  "error_code": null,
  "artifact_id": null,
  "policy_id": null,
  "validation_id": null
}
```

## 5. Metrics examples

Factory metrics:

- `factory_agent_runs_total`
- `factory_agent_run_failures_total`
- `factory_validation_gate_duration_seconds`
- `factory_validation_gate_failures_total`
- `factory_policy_denials_total`
- `factory_approval_pending_total`
- `factory_regeneration_diff_files_total`
- `factory_hallucination_or_unsupported_claims_total`

Application metrics:

- request count
- error count
- latency percentiles
- dependency call counts
- retry counts
- queue lag where applicable
- policy decision counts
- rejected unsafe input count

## 6. Trace design

A factory run trace should include spans for:

- requirement loading
- evidence retrieval
- policy check
- agent execution
- tool call
- artifact generation
- validation gate
- review
- debug/repair loop
- release evidence generation

## 7. Audit events

Audit events must be append-only for serious runs. Use `09_AUDIT_EVENT_SCHEMA.json`.

## 8. Debuggability requirement

A future engineer must be able to answer:

- What changed?
- Who/what changed it?
- Why was it changed?
- Which requirement/policy/task caused it?
- Which validation proved it?
- Which evidence supports it?
- What failed?
- How to reproduce?
- How to rollback?

If not, the observability standard is not met.
