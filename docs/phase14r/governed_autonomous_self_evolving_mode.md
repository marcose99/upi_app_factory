# Phase 14R — Governed Autonomous Self-Evolving Mode

Phase 14R turns the factory from a manually coordinated sequence of phase scripts into a governed autonomous self-evolving operating mode.

The operating goal is to let the factory complete future remaining phases with minimal human command-by-command involvement: autonomous planning, artifact generation, read-only gate execution, failure diagnosis, safe repair proposal, cataloged low-risk local repair application where policy allows, evidence creation, and continuation until a hard governance boundary is reached.

The mode is intentionally bounded. It may autonomously plan, generate local artifacts, run read-only validation gates, classify failures, propose repairs, and apply only cataloged low-risk local repairs in future phases. It must not autonomously merge, tag, push, release, promote, perform live-provider calls, perform destructive cleanup, or claim official certification.

## Operating model

1. **Plan** — create an evidence-backed phase plan and identify safe read-only gates.
2. **Execute read-only gates in parallel where safe** — run validators, targeted tests, static checks, and hygiene checks without changing repository state.
3. **Classify failures** — categorize failures into known safe repair classes, human-review-needed classes, or blocked classes.
4. **Self-evolve under governance** — propose improvements to prompts, policies, scripts, tests, documentation, and repair catalogs.
5. **Stop at irreversible boundaries** — merge, tag, push, release, promotion, certification, live calls, and destructive operations remain human-approved.

## Read-only parallelization boundary

Phase 14R permits parallel execution only for commands that are read-only with respect to repository state and external systems. Examples include validators, targeted pytest checks, Ruff, MyPy, policy checks, and audit inspection.

The factory must execute merge, tag, push, release, promotion, and certification decisions sequentially after successful evidence review.

## Self-evolution boundary

The factory may produce proposals and local patches for safe, low-risk improvements. It must preserve audit evidence showing what changed, why it changed, which gates passed, and which human-gated actions remain blocked.

## Certification boundary

The generated application may become certification-ready, but the factory does not certify it. Official certification remains the responsibility of independent authorities, auditors, regulators, and authorized certifying bodies.

## Learned safe repair class

- `mypy_validator_json_object_cast`: narrows JSON validator output from `Any` to `dict[str, Any]` using an explicit runtime object check and `typing.cast`, preserving MyPy strictness.

## Learned safe repair classes

- `validator_direct_script_import_path_bootstrap`: makes validators runnable as direct scripts by inserting the repository root into `sys.path` before importing `scripts.*`.

## Learned safe repair classes added during Phase 14R stabilization

- `validator_direct_execution_pythonpath_environment`
- `ruff_e402_import_order_cleanup`
