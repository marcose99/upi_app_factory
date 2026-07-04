# 12 — Debugging Playbook: Recover the Needle from the Haystack

Status: FINAL BASELINE v1.0

## 1. Debugging doctrine

Debugging must be forensic, not speculative.

A bug is not understood until it is reproducible or its non-reproducibility is explained with evidence.

## 2. Debug case creation

Create a debug case for every non-trivial failure.

Minimum fields:

- `debug_case_id`
- Symptom
- First observed time
- Affected run ID
- Affected task ID
- Expected behavior
- Actual behavior
- Reproduction command/steps
- Evidence inspected
- Hypotheses
- Confirmed root cause or `UNKNOWN`
- Fix
- Regression test
- Validation result
- Lessons learned

## 3. Failure classification

Use one primary classification:

- Requirement ambiguity
- Missing evidence
- Policy conflict
- Architecture gap
- Design gap
- Implementation bug
- Test bug
- Mock ecosystem bug
- Tool failure
- Environment issue
- Dependency issue
- Prompt issue
- Retrieval issue
- Hallucination/unsupported claim
- Governance bypass risk
- Observability gap
- Unknown

## 4. The forensic flow

1. Freeze failing state.
2. Assign `debug_case_id`.
3. Capture exact command and output.
4. Capture git status and recent diffs.
5. Identify last known good run.
6. Compare current run to last known good run.
7. Map symptom to requirement, policy, design, code, test, tool, and artifact.
8. Search by IDs first.
9. Search by failure text second.
10. Search by changed files third.
11. Search by policy IDs fourth.
12. Reproduce with smallest command.
13. Reduce to minimal input.
14. Determine whether failure is deterministic.
15. Confirm or falsify hypotheses.
16. Fix the smallest root cause.
17. Add regression protection.
18. Run targeted validation.
19. Run full validation if the change is accepted.
20. Update lessons learned.

## 5. Search order

Search in this order:

1. `run_id`
2. `task_id`
3. `validation_id`
4. `artifact_id`
5. `policy_id`
6. `requirement_id`
7. `trace_id`
8. `error_code`
9. failure string
10. changed files
11. recent commits
12. environment changes
13. dependency changes
14. prompt/agent changes
15. evidence source changes

## 6. Hypothesis discipline

Every hypothesis must have:

- Why it is plausible
- How to confirm it
- How to falsify it
- Evidence found
- Decision: kept or rejected

Never fix based on an untested hypothesis unless the risk is low and the change is independently validated.

## 7. Minimum commands to capture

Where applicable:

```bash
git status --short
git diff --stat
git diff
python --version
pip freeze
pytest -q
```

Project-specific commands must be added to `06_VALIDATION_GATES.yaml`.

## 8. Hallucination/unsupported claim debugging

If the issue is an unsupported claim:

1. Identify the exact claim.
2. Locate the alleged evidence.
3. Verify whether the evidence supports the claim.
4. Check if the claim came from model memory, retrieval, assumption, or prompt leakage.
5. Add a regression test or evaluator check.
6. Update prompt/policy/retrieval filters if needed.
7. Add the case to the golden regression suite.

## 9. Retrieval/RAG debugging

Inspect:

- Source document presence
- Parsing success
- Chunking strategy
- Embedding/index update
- Retrieval query
- Retrieved chunks
- Ranking
- Prompt assembly
- Answer grounding
- Unsupported content detector
- Citation alignment

## 10. Debug case closure criteria

Close only when:

- Root cause is confirmed or explicitly marked unknown with evidence.
- Fix is applied or mitigation accepted.
- Regression protection exists or justified as not applicable.
- Targeted validation passed.
- Full validation passed where required.
- Release notes/known limitations updated if relevant.
