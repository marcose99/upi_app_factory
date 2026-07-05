# Phase 11A.1 — Agentic Harness Essential Hardening

Phase 11A.1 adds essential operational controls before Phase 11B agent-generated
application code.

Run:

```bash
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python scripts/generate_phase11a1_harness_hardening.py
python scripts/validate_phase11a1_harness_hardening.py
```

Core principle:

```text
Agents generate proposals.
Deterministic validators judge.
Humans approve protected changes.
Git stores restore points.
```
