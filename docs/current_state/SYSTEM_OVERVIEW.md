# System Overview

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Explain what the factory is, who uses it, its two primary planes, supported local execution routes, safety boundaries, and where authoritative details live.<br>
> **Audience:** software architects, developers, testers, security reviewers, operators, recipients and technical decision-makers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- ISO/IEC/IEEE 42010:2022; C4/arc42 pragmatic modeling practices
- ISO/IEC/IEEE 26514:2022

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Mission and scope

UPI App Factory is a lightweight, governed, local-first software engineering factory for UPI applications. Generic architecture, engineering, governance, security, reproducibility and acceptance rules belong to the factory; application-specific runtime, test and environment details belong to per-application profiles. The current reference profile is `upi_dispute_resolution`. The accepted default route is deterministic and mock-safe. Real payment calls and live LLM execution are disabled by default; enabling production providers or payment rails is outside this documentation boundary.

The repository contains two related but distinct planes:

1. **Factory control / engineering plane** — requirements intake, planning, approval, application engineering, validation, evidence, portfolio/runtime control and operator surfaces.
2. **Engineered application runtime plane** — profile-selected materialized applications and their API/domain/application/infrastructure code, tests, local state, handover locks/contracts and runtime behavior. The currently verified reference instance is `upi_dispute_resolution`.

## Primary entrypoints

- Native recipient route: `./run_factory.sh`
- Factory startup implementation: `./start_factory.sh`
- Operator portal: `/operator-ui/` after successful health-gated startup
- Factory health: `GET /health`
- Docker/Compose route: `docker compose up --build`
- Docker shutdown: `docker compose down`
- Governed CI: `.github/workflows/governed-ci.yml`

## Runtime surface

Semantic normalization identifies **123 authoritative unique HTTP method/path keys** from **167 authoritative declarations**. Another **145** raw declarations belong to tests, fixtures, tooling or workspace/history and are excluded from the authoritative API count.

- AUTHORITATIVE_FACTORY_RUNTIME: 107 unique route keys
- AUTHORITATIVE_GENERATED_APPLICATION: 37 unique route keys

## Component estate

- CI_GOVERNANCE: 1 component groups
- FACTORY_PRODUCT: 59 component groups
- GENERATED_APPLICATION: 73 component groups
- REPOSITORY_SUPPORT: 15 component groups
- TESTS: 221 component groups
- TOOLING: 306 component groups
- WORKSPACE_OR_EVIDENCE: 1 component groups

The current reference generated application (`upi_dispute_resolution`) is present: **True**. Its app layer counts are `{"application": 5, "control_plane": 1, "disputes": 4, "domain": 5, "infrastructure": 9, "interfaces": 3, "observability": 3, "runtime.py": 1, "security": 3, "tests": 14, "upi_dispute_app": 15}`.

## Safety and non-claims

- Native hosting refuses non-loopback hosts.
- Docker publishes the portal to loopback on the host.
- `FACTORY_LLM_ENABLED=0` is asserted by the native route.
- `REAL_PAYMENT_CALLS=disabled` is asserted by the native route.
- Docker independently asserts LLM-off, real-payment-disabled and mock-boundary flags.
- Generated runtime child-process environments pass through a dedicated sanitization boundary that removes credential-like parent variables and reasserts safety controls.
- This repository is **not** evidence of a live UPI deployment, production provider integration, regulatory certification or formal standards certification.

## Canonical navigation

Start with [Documentation Index](../DOCUMENTATION_INDEX.md), then use [Architecture](ARCHITECTURE.md), [Quality Attributes](QUALITY_ATTRIBUTES.md), [Requirements and Traceability](../requirements/REQUIREMENTS_AND_TRACEABILITY.md), [Testing and Acceptance](../testing/TEST_STRATEGY_AND_ACCEPTANCE.md), [Security Architecture](../security/SECURITY_ARCHITECTURE_AND_THREAT_MODEL.md), [Operating Model](../operations/OPERATING_MODEL.md) and [Deployment](../deployment/LOCAL_AND_DOCKER_DEPLOYMENT.md).
