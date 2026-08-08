# Generated Application Local Deployment Guide

> **Status:** Canonical current-state documentation
> **Purpose:** Explain the generated application's independent local handover boundary.
> **Audience:** generated-application recipients, developers and reviewers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- SLSA 1.2 concepts; CycloneDX/SPDX SBOM concepts without level/certification claims

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


The authoritative generated application owns clean-room bootstrap/runtime-test locks and a dependency contract. Recipient proof must use the generated bundle's own bootstrap route rather than borrowing the factory repository `.venv`.

See [Generated Application Handover](../handover/GENERATED_APPLICATION_HANDOVER.md), the generated application's own `README.md`, and [Supply Chain and Dependencies](../security/SUPPLY_CHAIN_AND_DEPENDENCIES.md).

This is local reproducibility evidence, not production deployment approval.


## Recipient verification

From the generated application's recipient root, run:

```bash
PYTHONPATH=.. python -m pytest -q app/tests
```

This command is owned by `factory_governance/current_contracts/current_operational_contract.json`.
