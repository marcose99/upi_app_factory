# Test Strategy and Acceptance

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Describe current test levels, environments, data policy, acceptance gates and evidence expectations.<br>
> **Audience:** test engineers, developers, architects, SRE/operators, security reviewers and recipients<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 29119-3:2021
- ISO/IEC 25010:2023
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Current inventory

- Repository test files: **273**
- Repository `test_*` functions discovered statically: **1277**
- Generated-application test files: **3**
- Generated-application `test_*` functions discovered statically: **9**

Static counts are inventory aids; authoritative pass/fail comes from executed tests.

## Test levels and types

- Unit/component tests
- API/integration tests
- Generated-application acceptance tests
- Determinism and clean-room reproducibility tests
- Security and secret-boundary tests
- Dependency/supply-chain and SBOM/vulnerability checks
- Docker/platform contract tests
- Operator-portal behavioral tests
- Failure/recovery and governance tests
- Full regression

## Environments and data

Acceptance uses an isolated Python environment built from repository lock inputs, native loopback and Docker/Compose routes, mocked external systems and synthetic/fictional data. Live LLM and real payment calls remain disabled.

## Governed CI acceptance

The hosted `Governed CI` contract contains exactly seven jobs: Governance policy, Public clone hygiene, Ruff, MyPy, Focused tests, Docker platform contract and Full regression.

## Entry / exit

**Entry:** exact candidate identity, dependency consistency, required source/evidence available.<br>
**Exit:** required local gates and exact-head hosted CI pass with no blocker; protected delivery remains separately authorized.
