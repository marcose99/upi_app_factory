# Phase 14T — Autonomous Safe-Repair Catalog Operator Loop

Phase 14T turns the Phase 14R/14S autonomous mode into a catalog-driven operator loop for known low-risk failures.

The mode may autonomously diagnose failures, map them to a policy-cataloged repair class, apply only bounded low-risk local repairs, rerun impacted read-only gates, and produce evidence. It must stop for unknown failures or human-gated operations.

Human-gated boundaries remain mandatory for merge, tag, push, release, promotion, live-provider calls, destructive operations, and official certification claims.

The factory remains certification-ready-not-certified: it produces evidence for independent authority review but does not certify the generated application.

## Learned repair classes added during Phase 14T stabilization

- `mypy_redundant_cast_cleanup`: removes redundant test/validator casts only when MyPy already proves the inferred type satisfies the expected contract.
- `ruff_unused_import_cleanup`: removes unused imports after confirming the symbol is not referenced.
