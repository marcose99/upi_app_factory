# Operations and Acceptance

> **Status:** Canonical current-state documentation
> **Purpose:** Connect current operating guidance to governed acceptance evidence and release boundaries.
> **Audience:** operators, reviewers, release engineers and recipients
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC 20000-1:2018 and SRE practices
- ISO/IEC/IEEE 29119-3:2021
- ISO/IEC/IEEE 15289:2019

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Current operating guidance

Use [Operating Model](../operations/OPERATING_MODEL.md), [Observability and SLO Boundaries](../operations/OBSERVABILITY_AND_SLOS.md), [Incident and Recovery](../operations/INCIDENT_AND_RECOVERY.md) and [Local and Docker Deployment](../deployment/LOCAL_AND_DOCKER_DEPLOYMENT.md).

## Acceptance model

Acceptance is evidence-based: dependency closure, focused validators, security/supply-chain checks, Docker/platform contract, Ruff, MyPy and full regression must pass at the exact candidate. Hosted Governed CI must pass on the exact revision before a later protected delivery.

## Release boundary

Documentation reconstruction/qualification is not a merge, tag, GitHub release, deployment or certification claim. Documentation changes alter release identity and therefore require fresh RC requalification after delivery to `main`.
