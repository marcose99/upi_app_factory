# Quickstart

> **Status:** Canonical current-state documentation
> **Purpose:** Get a recipient from clean clone to the health-gated operator portal using the authoritative dependency route.
> **Audience:** new recipients and local operators
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


```bash
git clone <repository-url>
cd upi_app_factory
./run_factory.sh
```

Copy `<repository-url>` from GitHub's **Code** menu.

For a non-browser run:

```bash
./run_factory.sh --no-browser
```

The launcher manages `.venv` and exact dependency closure. When startup succeeds, use the printed local URL and `/operator-ui/`.

Stop the native portal cleanly with:

```bash
./stop_factory.sh
```

If you started with an explicit state root, pass the same state root to `stop_factory.sh`.

Docker alternative:

```bash
docker compose up --build
# stop:
docker compose down
```

Next read [Documentation Index](../DOCUMENTATION_INDEX.md).

## Legacy Phase 13C compatibility contract

The historical validator checks the phrases **git checkout** and **Validate baseline**. Current handover should use the exact governed revision supplied by release evidence; if a recipient is explicitly given a revision, `git checkout <exact-governed-revision>` is the generic Git operation, not an instruction to invent or choose a tag.

**Validate baseline** means verify the supplied exact revision/evidence and then use `./run_factory.sh`; it does not reinstate the older editable-development installation path.
