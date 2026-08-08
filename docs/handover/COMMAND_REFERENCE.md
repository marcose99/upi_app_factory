# Command Reference

> **Status:** Canonical current-state documentation
> **Purpose:** List current recipient/operator commands without historical phase-specific setup paths.
> **Audience:** recipients and operators
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Native

```bash
./run_factory.sh
./run_factory.sh --no-browser
./run_factory.sh --port 0
```

## Docker

```bash
docker compose up --build
docker compose down
```

## Maintainer quality checks

```bash
python -m ruff check .
python -m mypy .
python -m pytest -q
```

Exact environments must be created from repository lock inputs rather than unconstrained installation.

## Legacy Phase 13C compatibility contract — Current script equivalents

The historical future-CLI vocabulary included `./factory doctor` and `./factory generate`. These names are retained for validator/history compatibility only. Do not treat an unimplemented historical/future CLI spelling as a current executable command.

**Current script equivalents** are the repository-owned commands documented above and the operator portal/runtime surfaces verified at the checked-out revision.
