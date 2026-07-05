# Phase 10.2 — SDLC Technology Best-Practice Governance

Phase 10.2 creates a deterministic governance pack requiring future agents to
apply best practices appropriate to each software technology used in the
generated application's SDLC.

It generates:

- sdlc_technology_registry.json
- sdlc_best_practice_policy.md
- technology_specific_prompt_instructions.md
- sdlc_best_practice_traceability.json
- sdlc_best_practice_gap_report.json
- sdlc_best_practice_validation_report.json

Run:

```bash
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python scripts/generate_phase10_2_sdlc_best_practice_artifacts.py
python scripts/validate_phase10_2_sdlc_best_practice_artifacts.py
```

Boundary:

- official documentation links are reference candidates
- no runtime web fetching
- no unsupported version-specific claims
- no production/certification/compliance claim
- unsupported technology guidance remains MISSING_OFFICIAL_SOURCE
