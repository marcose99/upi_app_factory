# 11 — Regeneration Guide

Status: FINAL BASELINE v1.0

## 1. Goal

Regeneration must be repeatable, explainable, auditable, and comparable across runs.

The factory must never regenerate artifacts in a way that hides the previous state or destroys evidence.

## 2. Regeneration modes

| Mode | Purpose |
|---|---|
| `DRY_RUN` | Produce plan and expected artifacts only |
| `SHADOW_RUN` | Generate into isolated workspace without replacing baseline |
| `PATCH_PROPOSAL` | Produce deterministic diff for review |
| `APPLY_APPROVED_PATCH` | Apply approved changes to workspace |
| `RELEASE_REGENERATION` | Full release-grade regeneration with evidence pack |

## 3. Before regeneration

Capture:

- Timestamp UTC
- Git branch and commit
- Git status
- Dependency lockfile hashes
- Model/provider versions
- Prompt versions
- Agent role versions
- Policy versions
- Tool registry version
- Evidence source versions
- Task manifest
- Previous validation baseline
- Environment summary

Create:

- `source_input_snapshot.json`
- `policy_snapshot.json`
- `agent_prompt_snapshot.json`
- `tool_registry_snapshot.json`
- `dependency_snapshot.json`
- `baseline_validation_report.json`

## 4. During regeneration

For each task:

- Assign `task_id`
- Assign `agent_id`
- Record input hash
- Record output hash
- Record tool calls
- Record artifacts created/changed
- Record validation performed
- Record audit events
- Record failures and repairs

## 5. After regeneration

Create:

- `regeneration_manifest.json`
- `artifact_manifest.json`
- `validation_report.json`
- `audit_events.jsonl`
- `diff_summary.md`
- `known_limitations.md`
- `release_candidate_decision.md`

Compare with previous run:

- Added files
- Modified files
- Deleted files
- Changed requirements
- Changed policies
- Changed tests
- Changed behavior
- Changed validation results
- Changed evidence links

## 6. Acceptance decision

Classify the run:

- `ACCEPT`
- `ACCEPT_WITH_LIMITATIONS`
- `REPAIR_REQUIRED`
- `REJECT`
- `BLOCKED_PENDING_APPROVAL`

Acceptance is not allowed if:

- Validation blockers remain.
- Policy violations remain.
- Mock boundaries are hidden.
- Evidence is missing for release claims.
- High-risk approval is missing.
- Regression suite fails.

## 7. Regeneration manifest minimum fields

```json
{
  "regeneration_id": "REGEN-...",
  "timestamp_utc": "...",
  "mode": "SHADOW_RUN",
  "source_commit": "...",
  "target_branch": "...",
  "prompt_versions": [],
  "policy_versions": [],
  "tool_registry_version": "...",
  "evidence_snapshot_ids": [],
  "task_ids": [],
  "artifact_ids": [],
  "validation_ids": [],
  "audit_event_log": "audit_events.jsonl",
  "decision": "REPAIR_REQUIRED",
  "known_limitations": []
}
```

## 8. Golden rule

If two regeneration runs differ, the factory must be able to explain why by comparing inputs, policies, prompts, tools, dependencies, model versions, evidence snapshots, and task manifests.
