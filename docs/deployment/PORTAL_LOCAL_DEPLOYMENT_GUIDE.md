# Portal Local Deployment Guide

> **Status:** Canonical current-state documentation
> **Purpose:** Give current local portal startup and health guidance.
> **Audience:** operators and recipients
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC 20000-1:2018 and SRE practices

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Native

```bash
./run_factory.sh
```

The verified canonical UI route is `/operator-ui/` after `GET /health` succeeds.

## Docker

```bash
docker compose up --build
docker compose down
```

See [Local and Docker Deployment](LOCAL_AND_DOCKER_DEPLOYMENT.md) and [Operating Model](../operations/OPERATING_MODEL.md).
