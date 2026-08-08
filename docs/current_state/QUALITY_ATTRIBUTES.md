# Quality Attributes

> **Status:** Canonical current-state documentation<br>
> **Purpose:** State the quality concerns, evidence expectations and non-claims that shape architecture and acceptance.<br>
> **Audience:** architects, engineering leads, developers, testers, security reviewers and operators<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC 25010:2023
- ISO/IEC/IEEE 29148:2018
- ISO/IEC/IEEE 29119-3:2021

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Quality model

| Concern | Current engineering expectation | Evidence / acceptance route |
|---|---|---|
| Functional suitability | Governed requirements and accepted scenario contracts drive application engineering. | Full regression, focused validators, API/event contracts. |
| Reliability | Fail closed on invalid requirements, unsafe boundaries, dependency drift and protected-action ambiguity. | Tests, health checks, bounded repair/recovery evidence. |
| Security | Loopback local publication, mock/default-off external behavior, secret-boundary sanitation and dependency assurance. | Security tests, launcher/Compose/runtime controls. |
| Maintainability | Strict typing/linting, modular source, explicit contracts and source-traced documentation. | Ruff, MyPy, tests, source/document crosschecks. |
| Portability | Native Linux recipient route plus Docker/Compose portability route. | `run_factory.sh`, `compose.yaml`, Docker contract tests. |
| Usability / interaction | Operator portal exposes guarded actions, health/evidence surfaces and explicit outcomes. | Portal control contract and behavioral tests. |
| Performance efficiency | Acceptance remains lightweight/local and avoids heavyweight orchestration. | Local execution evidence; no production throughput/SLA claim. |
| Compatibility | HTTP/OpenAPI contracts and generated bundle locks isolate consumers from internals. | OpenAPI/tests/dependency contract. |
| Safety | No real payment calls in accepted default operation; live LLM/provider execution is default-off/policy-gated. | Launcher/container flags and runtime environment boundary. |

## Quality scenarios

1. Recipient dependency drift causes fail-closed lock verification and deterministic restoration from exact repository inputs.
2. Unsafe host exposure is rejected by the native launcher; Docker host publication remains loopback-only.
3. Generated runtime secret inheritance is bounded by credential-like environment filtering.
4. Real-payment and live-LLM execution remain disabled in accepted default routes.
5. Documentation/runtime drift is caught through source-truth matrices, documentation contracts and regression gates.
6. Release identity ambiguity fails closed through exact commit/tree/CI governance.

## Non-claims

No production availability, latency, throughput, RTO/RPO, regulatory certification or formal ISO conformity target is claimed unless separately measured and governed.
