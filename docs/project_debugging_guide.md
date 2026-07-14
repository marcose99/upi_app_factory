# Project Debugging Guide

This guide defines the debugging style for the `upi_app_factory` project.
It is intentionally beginner-readable and practical.

## Core rule

Debug from evidence, not from guessing.

Every debugging session should answer four questions:

1. What command failed?
2. What exact error appeared?
3. What changed since the last green restore point?
4. Which validation gate proves the fix?

## Golden debug loop

Use this loop for almost every problem:

```bash
# 1. Confirm location and environment
pwd
python --version
which python
git branch --show-current
git status --short

# 2. Reproduce with the smallest command
make validate

# 3. Isolate the failing layer
ruff check app factory tests
mypy app factory
pytest -q

# 4. Fix the smallest cause
# Edit one focused area only.

# 5. Re-run the smallest failing command
pytest -q tests/<specific_test_file>.py

# 6. Re-run the full gates
make validate
make validate-combined-phases
make validate-regeneration
make validate-baseline-provenance
make validate-factory-run

# 7. Commit only after the gates are green
git status --short
git diff --stat
```

## Beginner-friendly code standard

All generated code in this project should follow these rules:

1. Use clear names instead of clever names.
2. Prefer small functions with one purpose.
3. Keep validation near the boundary of the system.
4. Return structured data instead of unstructured strings when possible.
5. Raise errors with actionable messages.
6. Avoid hidden global state unless it is explicitly documented.
7. Add comments only where they explain intent, policy, or a non-obvious decision.
8. Keep deterministic scripts readable: preflight, write, validate, commit.
9. Make every generated artifact traceable to requirement, task, policy, and evidence where applicable.
10. Preserve honesty labels for mock, synthetic, missing-source, and limitation boundaries.

## Debug-friendly script pattern

Every automation script should prefer this structure:

```text
1. print project context
2. preflight safety checks
3. create or switch branch deliberately
4. write files deterministically
5. run focused tests
6. run full validation gates when practical
7. show git status and commit summary
8. avoid merge/tag unless the script is explicitly a release script
```

## Common project commands

```bash
cd /home/marcose/projects/upi_dispute_resolution_factory
source .venv/bin/activate

git status --short
git log --oneline --decorate -10
git tag --list

make validate
make validate-combined-phases
make validate-regeneration
make validate-baseline-provenance
make validate-factory-run
```

## Factory run debugging

```bash
RUN_ID=debug_review python scripts/run_governed_factory_run.py --force
python scripts/validate_factory_run_manifest.py \
  --run-dir workspace/runs/debug_review \
  --ignore-artifact-manifest-self-hash

find workspace/runs/debug_review -maxdepth 2 -type f | sort
cat workspace/runs/debug_review/factory_run_manifest.json | jq
cat workspace/runs/debug_review/task_manifest.json | jq
cat workspace/runs/debug_review/artifact_manifest.json | jq
cat workspace/runs/debug_review/validation_report.json | jq
head -20 workspace/runs/debug_review/audit_events.jsonl | jq
head -20 workspace/runs/debug_review/agent_outputs.jsonl | jq
```

## Failure triage map

| Symptom | First place to look | First command |
|---|---|---|
| Ruff failure | formatting, imports, unused code | `ruff check app factory tests` |
| MyPy failure | type contract mismatch | `mypy app factory` |
| Pytest failure | behavior or regression | `pytest -q` |
| Governance failure | policy/evidence pack | `make validate` |
| Regeneration failure | deterministic generator | `make validate-regeneration` |
| Factory run failure | run manifests or artifact traceability | `make validate-factory-run` |
| Git push failure | remote/authentication | `git remote -v` |

## What to collect before asking for help

Paste only relevant command output:

```bash
pwd
python --version
which python
git branch --show-current
git status --short
git log --oneline --decorate -5
<the failing command>
<the exact error output>
```

Do not paste secrets, private keys, tokens, passwords, full Aadhaar/PAN details, or production credentials.

## Debugging principles

1. Preserve the last stable tag before experimenting.
2. Never hide a mock boundary to make a demo look better.
3. Prefer one small reproducible failure over a large vague failure.
4. Validate after every meaningful change.
5. Keep logs useful but safe: enough detail for investigation, no secrets.
6. Prefer deterministic scripts over manual repair steps.
7. Record known limitations honestly instead of burying them.
8. When in doubt, create evidence before creating code.

## References

- NIST SP 800-218 Secure Software Development Framework: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- OWASP Error Handling Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html
- Google Developer Documentation Style Guide: https://developers.google.com/style
