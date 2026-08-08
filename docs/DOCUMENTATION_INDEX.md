# Documentation Index

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Provide one authoritative navigation point for current documentation and clearly separate current guidance from historical/duplicative evidence.<br>
> **Audience:** all repository readers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- ISO/IEC/IEEE 26514:2022

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Canonical current documentation

### Understand the system

- [System Overview](current_state/SYSTEM_OVERVIEW.md)
- [Current Architecture](current_state/ARCHITECTURE.md)
- [Quality Attributes](current_state/QUALITY_ATTRIBUTES.md)
- [Requirements and Traceability](requirements/REQUIREMENTS_AND_TRACEABILITY.md)
- [Test Strategy and Acceptance](testing/TEST_STRATEGY_AND_ACCEPTANCE.md)

### Security and supply chain

- [Security Architecture and Threat Model](security/SECURITY_ARCHITECTURE_AND_THREAT_MODEL.md)
- [Supply Chain and Dependencies](security/SUPPLY_CHAIN_AND_DEPENDENCIES.md)
- [AI and Agentic Governance](ai/AI_AND_AGENTIC_GOVERNANCE.md)

### Operate and deploy

- [Operating Model](operations/OPERATING_MODEL.md)
- [Observability and SLO Boundaries](operations/OBSERVABILITY_AND_SLOS.md)
- [Incident and Recovery](operations/INCIDENT_AND_RECOVERY.md)
- [Local and Docker Deployment](deployment/LOCAL_AND_DOCKER_DEPLOYMENT.md)
- [API and Event Contracts](api/API_AND_EVENT_CONTRACTS.md)

### Governance and handover

- [Release Governance](governance/RELEASE_GOVERNANCE.md)
- [Handover index](handover/README_HANDOVER.md)

## Document lifecycle

`docs/documentation/DOCUMENTATION_EVIDENCE_MATRIX.json` is the machine-readable lifecycle inventory.

- **CURRENT_AND_VERIFIED** — current guidance or contract; must remain source-truth accurate.
- **DUPLICATIVE_CONSOLIDATE** — retained content that must not compete with canonical current guidance.
- **HISTORICAL_RETAIN_AS_HISTORY** — provenance/history; old phase status is not current capability.

Historical phase/capstone/ADR evidence is intentionally retained and not silently rewritten into present tense.
