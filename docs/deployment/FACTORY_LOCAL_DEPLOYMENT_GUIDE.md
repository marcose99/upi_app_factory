# Factory Local Deployment Guide

> **Status:** Canonical current-state documentation
> **Purpose:** Provide the current native recipient command and point to the complete deployment contract.
> **Audience:** recipients and operators
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC 20000-1:2018 and SRE practices

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Native route

```bash
git clone <repository-url>
cd upi_app_factory
./run_factory.sh
```

For non-browser startup:

```bash
./run_factory.sh --no-browser
```

The launcher owns `.venv` creation and exact dependency closure. Do not substitute an editable development install as the recipient handover route.

Full details: [Local and Docker Deployment](LOCAL_AND_DOCKER_DEPLOYMENT.md).
