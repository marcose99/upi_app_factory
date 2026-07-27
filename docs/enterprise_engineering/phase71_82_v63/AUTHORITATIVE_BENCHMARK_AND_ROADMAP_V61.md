# UPI App Factory Enterprise Engineering Benchmark and Governed Campaign V63

**Research and preparation date:** 2026-07-25  
**Immutable public baseline:** `5373b9bdd04ccd7760e65345d311362c5bc9a48f`  
**Required posture:** local-first, deterministic-first, evidence-driven, mock-only, lightweight, certification-ready-not-certified.  
**Protected actions:** no merge, push to `main`, release, deployment, certification claim or destructive cleanup without explicit human approval.

## 1. Current status and truth boundary

This document is the research benchmark, evidence-based preliminary code review, adapted Phase 71–82 roadmap and standalone governed execution controller.

It is **not** the final candidate review. The V60 campaign has not been executed against the user's canonical local repository in this environment, so no feature branch, worktree or candidate commit is claimed here. The exact final stop marker must be emitted only by a successful local V60 run after all gates pass.

The public `main` commit `5373b9bdd04ccd7760e65345d311362c5bc9a48f` is treated as immutable. The campaign must create a fresh retained feature branch from that exact commit and prove that local `main`, `origin/main` and public `main` remain unchanged.

## 2. How statements are classified

### 2.1 Authoritative benchmark

A control is authoritative when it is derived from a published standard, final government guidance, IETF/W3C/OpenID specification or the current official project specification. Drafts and beta maturity models are clearly marked informative or advisory.

### 2.2 Engineering opinion

An opinion is a reasoned interpretation of how to satisfy a capability while preserving this factory's constraints. Examples: using SQLite outbox instead of mandatory Kafka, native typed policy before OPA, and local deterministic OIDC testing instead of mandatory Keycloak.

### 2.3 Recommendation

A recommendation is proposed work whose value must be proven through generated code, tests, evidence and exact-candidate acceptance. Recommendations do not become facts merely because they appear in documentation.

## 3. Authoritative and industry-trusted source catalog

| ID | Authority | Status | Application | Official source |
| --- | --- | --- | --- | --- |
| ISO-12207-2026 | International standard | Published | Lifecycle processes, traceability, assurance, maintenance and retirement. | https://www.iso.org/standard/90219.html |
| ISO-25010-2023 | International standard | Published | Measurable quality characteristics and quality requirements. | https://www.iso.org/standard/78176.html |
| ISO-42010-2022 | International standard | Published | Stakeholders, concerns, viewpoints, decisions and model consistency. | https://www.iso.org/standard/74393.html |
| ISO-5055-2021 | International standard | Published | Structural quality, reliability, security, performance and maintainability weaknesses. | https://www.iso.org/standard/80623.html |
| ISO-27001-2022 | International standard | Published | Risk-governed security-management overlay; no certification claim. | https://www.iso.org/standard/82875.html |
| ISO-42001-2023 | International standard | Published | AI accountability, risk, monitoring and continual improvement. | https://www.iso.org/standard/81230.html |
| NIST-SSDF-1.1 | US government standard guidance | Final | Secure development practices and evidence integrated into any SDLC. | https://csrc.nist.gov/pubs/sp/800/218/final |
| NIST-SSDF-1.2-IPD | US government draft | Initial public draft; informative only | Forward-looking delta only; must not replace final SSDF 1.1 for closure. | https://csrc.nist.gov/pubs/sp/800/218/r1/ipd |
| NIST-800-204 | US government standard guidance | Final | Microservice identity, communication, resilience, monitoring and access control. | https://csrc.nist.gov/pubs/sp/800/204/final |
| NIST-800-204C | US government standard guidance | Final | Application, services, infrastructure, policy and observability as code. | https://csrc.nist.gov/pubs/sp/800/204/c/final |
| NIST-800-204D | US government standard guidance | Final | Supply-chain controls integrated into microservice delivery pipelines. | https://csrc.nist.gov/pubs/sp/800/204/d/final |
| OWASP-ASVS-5.0 | Industry verification standard | Released | Testable application-security requirements; Level 2 default target. | https://owasp.org/www-project-application-security-verification-standard/ |
| OWASP-SAMM-2.0.3 | Industry maturity model | Released | Risk-driven governance, design, implementation, verification and operations maturity. | https://owasp.org/www-project-samm/ |
| OWASP-TOP10-2025 | Industry awareness baseline | Released | Awareness cross-check; not a substitute for ASVS verification. | https://owasp.org/Top10/2025/ |
| OWASP-API-2023 | Industry API-risk baseline | Released | Authorization, authentication, resource consumption, inventory and unsafe consumption. | https://owasp.org/API-Security/editions/2023/en/0x11-t10/ |
| OPENSSF-OSPS-2025-10-10 | Open-source security baseline | Released | Tiered repository, build, release, governance and vulnerability controls. | https://baseline.openssf.org/versions/2025-10-10.html |
| OPENSSF-SCORECARD | Open-source automated assessment | Current | Repository-security checks; advisory evidence, not certification. | https://openssf.org/projects/scorecard/ |
| SLSA-1.2 | Industry supply-chain specification | Approved | Source/build provenance, verification and tamper resistance. | https://slsa.dev/spec/v1.2/ |
| CYCLONEDX-1.7 | Industry/ECMA SBOM standard | Released | SBOM, services, vulnerabilities, formulation and attestations. | https://cyclonedx.org/specification/overview/ |
| SPDX-3.0 | Linux Foundation/ISO SBOM standard | Current | Interoperable component, license and provenance representation. | https://spdx.dev/use/specifications/ |
| REPRODUCIBLE-BUILDS | Industry reproducibility guidance | Current | Same-source/same-environment artifact identity and variance diagnosis. | https://reproducible-builds.org/docs/definition/ |
| OPENAPI-3.2.0 | Linux Foundation API specification | Published | HTTP API contracts; generated output may truthfully remain 3.1 where tooling requires. | https://spec.openapis.org/oas/v3.2.0.html |
| ASYNCAPI-3.1.0 | Linux Foundation event API specification | Published | Machine-readable event/message contracts where asynchronous collaboration is justified. | https://www.asyncapi.com/docs/reference/specification/latest |
| RFC-9457 | IETF standard-track RFC | Published | Standard application/problem error media type and fields. | https://www.rfc-editor.org/rfc/rfc9457.html |
| RFC-9700 | IETF Best Current Practice | Published | OAuth security profile, PKCE, redirect matching, token audience and deprecated-flow avoidance. | https://www.rfc-editor.org/rfc/rfc9700.html |
| OIDC-CORE-1.0 | OpenID Foundation specification | Final | Authentication and identity claims over OAuth 2.0. | https://openid.net/specs/openid-connect-core-1_0.html |
| OTEL-1.59.0 | CNCF observability specification | Current | Vendor-neutral traces, metrics, logs, resources, baggage and context. | https://opentelemetry.io/docs/specs/otel/ |
| PROMETHEUS-NAMING | CNCF project guidance | Current | Metric names, units, suffixes, labels and cardinality. | https://prometheus.io/docs/practices/naming/ |
| W3C-TRACE-CONTEXT | W3C specification | Recommendation-track | traceparent/tracestate interoperability. | https://www.w3.org/TR/trace-context/ |
| DORA | Industry research program | Current | Delivery throughput and instability measures, interpreted with quality outcomes. | https://dora.dev/guides/dora-metrics/ |
| GOOGLE-SRE | Industry reference | Current | SLIs, SLOs, error budgets and user-centered reliability. | https://sre.google/sre-book/service-level-objectives/ |
| TWELVE-FACTOR | Industry methodology | Advisory | Selective portability principles; must not override audit retention or domain integrity. | https://12factor.net/ |
| CNCF-MATURITY | CNCF advisory guidance | 4.0 beta | People/process/policy/technology/business maturity cross-check; not a normative gate. | https://maturitymodel.cncf.io/ |
| AZURE-WAF | Cloud-provider architecture guidance | Current | Provider-neutral cross-check of reliability, security, cost, operations and performance. | https://learn.microsoft.com/en-us/azure/well-architected/ |
| AWS-WAF | Cloud-provider architecture guidance | Current | Provider-neutral cross-check of six architecture pillars. | https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html |
| OPA | CNCF policy engine guidance | Current | Policy-as-code principles; implementation may remain typed native Python/JSON unless OPA adds net value. | https://www.openpolicyagent.org/docs/latest/ |
| OPENGITOPS | CNCF working-group principles | Current | Declarative/versioned/pulled/reconciled delivery applicability; no cluster requirement. | https://opengitops.dev/ |

## 4. Production microservice benchmark matrix

| Control | Domain | Level | Sources | Factory requirement |
| --- | --- | --- | --- | --- |
| LIFE-01 | Lifecycle traceability | MUST | ISO-12207-2026, NIST-SSDF-1.1 | Requirements → architecture decisions → generated code → tests → evidence → operations/retirement must be linked and machine-checkable. |
| ARCH-01 | Architecture description integrity | MUST | ISO-42010-2022 | Generate stakeholders, concerns, viewpoints, bounded contexts, decisions, trade-offs and synchronized diagrams/models. |
| QUAL-01 | Product quality model | MUST | ISO-25010-2023 | Define measurable requirements for functionality, performance, compatibility, interaction, reliability, security, maintainability, flexibility and safety. |
| QUAL-02 | Structural quality | MUST | ISO-5055-2021 | Enforce dependency boundaries, complexity budgets, architectural rules and technical-debt evidence. |
| MSA-01 | Bounded service ownership | MUST | NIST-800-204, ISO-42010-2022 | Each generated service has explicit responsibility, data ownership, APIs/events, dependencies and independent tests. |
| MSA-02 | Data consistency | MUST | NIST-800-204C | Use optimistic concurrency, idempotency and explicit consistency boundaries; use outbox/inbox and compensation where workflows cross services. |
| API-01 | HTTP contract | MUST | OPENAPI-3.2.0 | Generate OpenAPI 3.1+ with truthful tooling version, operation IDs, examples, security schemes, pagination and compatibility evidence. |
| API-02 | Problem details | MUST | RFC-9457 | All generated API errors use application/problem+json-compatible stable types, status, title, detail, instance and correlation extensions. |
| EVT-01 | Event contracts | SHOULD | ASYNCAPI-3.1.0 | When eventing is justified, generate AsyncAPI and a portable envelope; otherwise record a reasoned not-applicable decision. |
| SEC-01 | Application verification | MUST | OWASP-ASVS-5.0, OWASP-SAMM-2.0.3 | Target ASVS Level 2 and maintain a measurable SAMM improvement plan with evidence, exclusions and risk ownership. |
| SEC-02 | API abuse resistance | MUST | OWASP-API-2023, OWASP-TOP10-2025 | Verify object/function/property authorization, resource limits, inventory, SSRF, unsafe consumption and secure defaults. |
| IAM-01 | OAuth/OIDC profile | MUST | RFC-9700, OIDC-CORE-1.0 | Generate an identity/authorization adapter contract and deterministic local test issuer; production issuer integration remains optional and gated. |
| REL-01 | SLOs and failure semantics | MUST | GOOGLE-SRE | Generate SLIs/SLOs/error budgets plus timeout, retry, jitter, circuit-breaker, bulkhead, rate-limit and degraded-mode policies. |
| REL-02 | Runtime lifecycle | MUST | NIST-800-204 | Distinct startup, liveness and readiness probes; graceful drain/shutdown and restart/recovery tests. |
| OBS-01 | Structured telemetry | MUST | OTEL-1.59.0, W3C-TRACE-CONTEXT | Correlated logs, metrics and traces with stable service/resource attributes and safe cardinality. |
| OBS-02 | Prometheus compatibility | MUST | PROMETHEUS-NAMING | Expose OpenMetrics/Prometheus-compatible counters/histograms using base units, _total suffixes and bounded labels. |
| TEST-01 | Layered verification | MUST | ISO-12207-2026, OWASP-ASVS-5.0 | Unit, component, integration, provider/consumer contract, end-to-end, security, migration, restart and operational acceptance tests. |
| TEST-02 | Adversarial and statistical depth | SHOULD | ISO-5055-2021, NIST-SSDF-1.1 | Use deterministic fuzz/property/mutation/model-based tests where they materially improve confidence. |
| PERF-01 | Performance/capacity evidence | MUST | ISO-25010-2023, GOOGLE-SRE | Local repeatable smoke/load tests with percentile, concurrency and resource budgets; no production-capacity claim from laptop results. |
| SUP-01 | Dependency governance | MUST | NIST-800-204D, OPENSSF-OSPS-2025-10-10 | Pinned/locked reviewed dependencies, source restrictions, license evidence, update policy and minimal runtime footprint. |
| SUP-02 | SBOM interoperability | MUST | CYCLONEDX-1.7, SPDX-3.0 | Produce and validate CycloneDX and SPDX representations for factory and each generated deliverable. |
| SUP-03 | Provenance | MUST | SLSA-1.2 | Produce verifiable source/build provenance and verification summaries without claiming a SLSA level unless all requirements are satisfied. |
| SUP-04 | Reproducible artifacts | MUST | REPRODUCIBLE-BUILDS | Normalize timestamps/order/metadata, rebuild twice, compare hashes and explain unavoidable variance. |
| POL-01 | Policy and approvals | MUST | OPA, NIST-SSDF-1.1 | Typed policy decisions, scope-bound approval, nonce/replay protection and fail-closed protected-action enforcement. |
| GITOPS-01 | GitOps applicability | SHOULD | OPENGITOPS | Adopt declarative/versioned/reconciled principles for delivery evidence only where useful; Kubernetes and continuous deployment remain unnecessary. |
| PORT-01 | Portfolio isolation | SHOULD | CNCF-MATURITY, ISO-25010-2023 | Multi-application isolation for state, ports, process ownership, quotas and evidence before any full multi-tenant productization. |
| OPS-01 | Delivery performance | SHOULD | DORA | Measure delivery and recovery without gaming metrics and correlate with quality/reliability. |
| OPS-02 | Operational readiness | MUST | GOOGLE-SRE, AZURE-WAF, AWS-WAF | Runbooks, rollback, incident timeline, recovery objectives, ownership and provider-neutral well-architected review. |
| AI-01 | Governed agent orchestration | MUST | ISO-42001-2023, NIST-SSDF-1.1 | Versioned prompts/schemas/tools, bounded loops, least privilege, independent verification, no silent self-modification and explicit protected-action approvals. |
| LIGHT-01 | Lightweight portability | MUST | TWELVE-FACTOR, CNCF-MATURITY | Capability depth without mandatory Kubernetes, mesh, Kafka, Redis, PostgreSQL or cloud services; native and container routes stay first-class. |

### 4.1 Applicability decisions

- **Twelve-Factor:** adopt externalized configuration, explicit dependencies, port binding, disposability and environment parity concepts. Do not blindly apply the “logs as event streams only” interpretation to immutable audit/evidence records.
- **CNCF maturity:** use as an advisory organizational/platform maturity cross-check, not as a certification gate and not as justification for Kubernetes.
- **AWS/Azure Well-Architected:** use provider-neutral pillar reviews only; do not introduce provider services.
- **GitOps:** adopt declarative/versioned desired-state and verification concepts. Do not add continuous deployment, cluster reconciliation or Kubernetes.
- **Policy as code:** typed native Python/JSON policy and schema validation remain valid. Introduce OPA only when cross-language or externalized policy reuse measurably warrants it.
- **OpenAPI 3.2:** benchmark against 3.2, but generated applications may truthfully emit 3.1 where FastAPI/tooling compatibility requires it. The limitation and upgrade path must be evidenced.
- **AsyncAPI/eventing:** required only where asynchronous collaboration has engineering value. A documented not-applicable decision is better than artificial event complexity.
- **Docker:** a supported recipient route, not a mandatory architecture or closure dependency when Docker is unavailable. Native exact-candidate acceptance remains mandatory.

## 5. Public baseline: strengths that must not regress

- The public repository already implements deterministic-first operation, explicit approvals, immutable identities, evidence hashes, mock-only integrations and fail-closed non-claims.
- The reference generated application has clear domain/application/infrastructure seams through CQRS objects, ports, repository and unit-of-work abstractions.
- SQLite is a justified lightweight default for local-first operation and can support production-quality transaction/outbox semantics for the intended constrained runtime.
- The generated application already implements client-request and business-level duplicate detection and returns an idempotent replay for identical submissions.
- Runtime configuration prohibits live providers and real secrets and constrains persistence paths.
- The repository has structured logging, PII-sensitive-key handling and W3C trace-context parsing in factory observability code.
- The repository has extensive factory-wide regression, native recipient and Docker/Compose routes, generated test execution, OpenAPI publication and runtime operations evidence.
- The current README truthfully states that the project is not production-deployed, certified or approved for real payment movement.

## 6. Confirmed engineering gaps

The following are not cosmetic observations. They are grounded in the public reference generated application or the prior V59 campaign design. The local V60 discovery stage must verify scope, generator propagation and whether other repository components already address any item.

| Gap | Severity | Evidence status | Engineering impact | Required work |
| --- | --- | --- | --- | --- |
| GAP-API-PROBLEM-DETAILS | HIGH | CONFIRMED_PUBLIC_CODE | Consumers cannot rely on RFC 9457 media type/fields; error compatibility and observability are weaker. | Generate RFC 9457 problem types, correlation extension, safe validation details, OpenAPI examples and compatibility tests. |
| GAP-IAM-BOUNDARY | HIGH | CONFIRMED_REFERENCE_GENERATED_APP | The application is appropriate for local simulation, not a production-oriented security blueprint. | Generate a lightweight identity port, local deterministic signed-token test profile, role/scope policy, OpenAPI security scheme and RFC 9700/OIDC production-adapter contract. |
| GAP-HEALTH-LIFECYCLE | HIGH | CONFIRMED_PUBLIC_CODE | Dependency failure, startup failure and graceful termination cannot be represented or tested precisely. | Generate startup/liveness/readiness endpoints, dependency checks, lifespan hooks, drain state and graceful-shutdown/restart tests. |
| GAP-METRICS | HIGH | CONFIRMED_PUBLIC_CODE | No Prometheus/OpenMetrics interoperability, latency histograms, bounded labels, persistence semantics or SLO derivation. | Add lightweight text exposition, naming/unit/cardinality validation, request/latency/error/business metrics and tests without adding a mandatory monitoring backend. |
| GAP-EVENT-DURABILITY | CRITICAL | CONFIRMED_PUBLIC_CODE | A crash after database commit can lose integration intent; duplicate delivery and replay cannot be governed. | Generate transactional outbox/inbox tables, event envelope/version, deterministic dispatcher, retry/dead-letter evidence, CloudEvents/AsyncAPI artifacts and crash/replay tests. |
| GAP-TRANSACTION-SEMANTICS | CRITICAL | CONFIRMED_PUBLIC_CODE | The abstraction does not provide atomic application service, audit and event persistence or reliable rollback. | Move commits out of repositories, implement explicit transaction boundaries/context manager and atomically persist aggregate, audit reference and outbox record. |
| GAP-MIGRATIONS | HIGH | CONFIRMED_PUBLIC_CODE | Schema evolution, rollback, upgrade testing and evidence are not deterministic enough for long-lived services. | Generate a lightweight ordered SQLite migration ledger with checksums, upgrade validation, rollback policy and migration/restart tests. |
| GAP-CONCURRENCY | HIGH | CONFIRMED_REFERENCE_GENERATED_APP | Concurrent updates can overwrite state or create non-deterministic behavior. | Generate aggregate versions, optimistic compare-and-swap updates, HTTP conditional request support and concurrency tests. |
| GAP-API-OPERABILITY | MEDIUM | CONFIRMED_REFERENCE_GENERATED_APP | Resource consumption and API evolution are not bounded. | Generate cursor/limit contracts, maximum page size, rate/resource policy interface, 429 problem details and abuse tests. |
| GAP-RESILIENCE-ADAPTERS | HIGH | CONFIRMED_BLUEPRINT_LIMITATION | A future real adapter could be added without safe failure semantics. | Generate a dependency-call policy and standard-library lightweight resilience primitives, deterministic fake clock/failure tests, and require every adapter to declare budgets. |
| GAP-GENERATED-TEST-DEPTH | HIGH | CONFIRMED_REFERENCE_TREE_WITH_REPOSITORY_WIDE_AUDIT_REQUIRED | Factory-wide regression depth is strong, but generated deliverables themselves do not yet prove all production-oriented properties. | Generate self-contained test layers and evidence for every blueprint capability; never rely only on factory tests. |
| GAP-SUPPLY-CHAIN | HIGH | CONFIRMED_DOCUMENTED_LIMITATION_PLUS_AUDIT_REQUIRED | Component identity, repeatability and artifact trust are incomplete until exact candidate evidence proves them. | Generate dual SBOMs, build manifest, reproducibility comparison, signed/unsigned verification modes and SLSA-style provenance without claiming an attained level prematurely. |
| GAP-BENCHMARK-CONTROL-PLANE | HIGH | CONFIRMED_V59_CAMPAIGN_DESIGN | A campaign could close against an incomplete or stale benchmark and report an incorrect state. | Use V60 dated source catalog, final/draft distinction, applicability decisions, score >=90, independent reviews and exact `READY_FOR_GOVERNED_REVIEW` marker. |
| GAP-AUTHORITY-SEPARATION | MEDIUM | CONFIRMED_V59_CAMPAIGN_DESIGN | Readers can confuse standards requirements with design choices. | Generate separate authoritative benchmark, engineering opinion and recommendation/roadmap documents with source and rationale fields. |

### 6.1 Code-level evidence summary

1. **Custom errors instead of RFC 9457.** `errors.py` produces a nested `error` object, and `main.py` exception handlers return that structure. This is stable and readable but not the standard problem-details contract.
2. **No generated identity boundary.** The reference generated routes use no authentication/authorization dependency or OpenAPI security scheme. That is safe for a loopback simulation but not a production-oriented blueprint.
3. **Health semantics are collapsed.** `/health` and `/runtime/health` do not distinguish startup, liveness and readiness or expose drain state.
4. **Metrics are local counters.** `/runtime/metrics` returns in-memory JSON counters, not OpenMetrics/Prometheus exposition or latency histograms.
5. **Events are not durable.** `DomainEventCollector` is an in-memory list. State is committed before events are recorded into audit details, so crash-safe integration intent is not guaranteed.
6. **Unit of work is nominal.** Repository methods commit internally, followed by another unit-of-work commit. The abstraction cannot atomically coordinate aggregate, audit and outbox state.
7. **Schema evolution is inline.** Runtime `CREATE TABLE` and conditional `ALTER TABLE` logic has no explicit migration version/checksum ledger.
8. **No optimistic concurrency.** Aggregate versions, conditional updates and HTTP ETag/If-Match semantics are absent in the public reference package.
9. **Unbounded collection API.** `GET /disputes` returns all records with no visible pagination or maximum resource policy.
10. **Generated test depth needs expansion.** The visible generated test tree proves API/PII/workflow/scenario behavior but does not itself show migration, contract evolution, crash recovery, concurrency, authz, performance or durable-event replay suites.
11. **Current supply-chain closure is incomplete.** The README itself lists signed artifact/provenance verification as a next improvement. Current SLSA 1.2, CycloneDX 1.7 and SPDX 3.0 evidence must therefore be generated and verified rather than claimed.
12. **The previous campaign benchmark was stale/incomplete.** V59 used SLSA 1.1 and did not explicitly cover SAMM, OpenSSF, OAuth/OIDC, Prometheus, SPDX, Well-Architected or OpenGitOps, and its success marker did not match the required marker.

## 7. Engineering opinions

- A production-grade microservice is defined by independently owned contracts, data, failure semantics, operability, security and release evidence—not by creating many processes.
- The first priority is a **production microservice blueprint kernel** that can generate one excellent service and then safely compose multiple services.
- SQLite remains appropriate as the mandatory lightweight store. It can provide migrations, optimistic concurrency, outbox/inbox, lease tables and durable audit indices without adding infrastructure.
- Kafka, Redis, PostgreSQL, a service mesh and Kubernetes should be optional adapters, introduced only by requirement and justified capacity/failure analysis.
- The factory should generate **capability-neutral ports plus deterministic local implementations**. Production adapters are contracts and optional packages, never implicit live connectivity.
- Generated applications must carry their own test and evidence packs. Factory-wide regression cannot substitute for deliverable-level proof.
- Self-improvement must be an offline, evaluated proposal/repair loop with immutable before/after evidence. It must never silently alter prompts, policies, tests or protected-action rules.

## 8. Adapted Phase 71–82 roadmap

{md_table(["Phase", "Remembered theme", "Decision", "Modern disposition"], phase_rows)}

## 9. Governed implementation campaign

### A — Benchmark and control plane

**Objective:** Establish current source catalog, final/draft handling, applicability decisions, gap register, policy schema and traceability.

**Exit gates**
- All benchmark sources dated and classified.
- Authoritative/opinion/recommendation artifacts separate.
- Every MUST control has evidence or explicit gap.
- No main mutation; fresh retained branch/worktree exact parent.

### B — Generated microservice kernel

**Objective:** Implement generated migrations, real unit-of-work, optimistic concurrency, RFC 9457 and lifecycle probes.

**Exit gates**
- Repository methods do not commit internally.
- Aggregate + audit reference + outbox are atomic.
- Migration upgrade/replay tests pass.
- Startup/liveness/readiness/graceful-stop tests pass.
- Generator and fresh generated application are byte/evidence consistent.

### C — Contract, identity and adapter engineering

**Objective:** Generate OpenAPI compatibility evidence, OAuth/OIDC port/local test profile, AsyncAPI/CloudEvents where applicable and resilient adapter contracts.

**Exit gates**
- OpenAPI validates and contract-diff gate passes.
- RFC 9700 security-profile tests pass.
- Object/function authorization tests pass.
- Every dependency call has timeout/retry/breaker/budget declaration.
- Mock-only boundary remains fail-closed.

### D — Reliability, observability and operability

**Objective:** Generate SLIs/SLOs, Prometheus-compatible metrics, trace propagation, safe structured logs, runbooks and failure-mode tests.

**Exit gates**
- Latency/error/business metrics have naming/cardinality tests.
- W3C trace context propagates through HTTP and event envelopes.
- Crash, duplicate, retry exhaustion, stale state and restart tests pass.
- Local performance budgets pass without production capacity claims.

### E — Security and supply chain

**Objective:** ASVS Level 2 mapping, threat model, SBOMs, reproducible package, provenance and policy gates.

**Exit gates**
- No unresolved critical/high ASVS/API findings.
- CycloneDX 1.7 and SPDX 3.0 validate.
- Two clean builds compare identically or explain approved variance.
- SLSA-style provenance verifies; no unattained level claim.
- OpenSSF baseline/Scorecard findings are recorded and triaged.

### F — Portfolio and governed agents

**Objective:** Multi-application isolation, recommendation-only portfolio intelligence, bounded repair, immutable evaluation and approval replay protection.

**Exit gates**
- Concurrent apps have isolated ports/state/process/evidence.
- Approval scope and nonce replay tests pass.
- Agent outputs are schema-validated and independently checked.
- No protected Git or deployment action is reachable without explicit human approval.

### G — Enterprise capstone

**Objective:** Independent exact-candidate acceptance and evidence sealing.

**Exit gates**
- Candidate is a direct child of baseline and worktree is clean.
- Baseline and candidate complete regressions pass with no weakened tests.
- Fresh requirements-to-application E2E passes natively.
- Docker/Compose is validated when available but is not a mandatory architectural dependency.
- Independent architecture and security reviewers score >=90 with zero critical gaps.
- Public main and remote refs remain unchanged.
- Exact terminal marker is emitted only after all gates pass.

## 10. Non-negotiable implementation rules

- Start from exact, clean `{baseline}` and create one fresh retained branch/worktree.
- No implementation on canonical `main`.
- No merge, push, force-push, tag, release, deployment, certification claim, branch deletion or worktree deletion.
- No dependency or test weakening merely to obtain green status.
- Every implementation must update the generator/blueprint and prove fresh generated output; patching only the tracked reference application is insufficient.
- Existing dependencies and standard library are preferred. Any proposed new dependency must have a quantified benefit, license/security review and explicit human approval.
- Live banks, PSPs, NPCI/UPI rails, RBI systems, identity providers and OpenAI calls remain disabled unless separately approved; payment integrations remain mock/simulated.
- Detailed logs go to evidence files; console output shows stages, pass/fail, first authoritative failure, candidate identity and evidence paths.
- Repeated unchanged failures must stop bounded repair rather than consume cycles blindly.
- Docker unavailability cannot force architecture changes; it becomes an explicitly skipped optional lane with evidence.
- The branch/worktree and evidence remain available for governed review.


## 11. Standalone V63 controller architecture

V63 is self-contained. It does not require V59, V60, or any other previously downloaded campaign controller.

It performs:

1. exact-baseline and immutable-main verification;
2. live `origin/main` verification;
3. fresh retained branch and Git worktree creation;
4. controller self-copy and resumable state creation;
5. repository-aware hydration planning;
6. complete baseline regression and test-count capture;
7. benchmark, opinion, recommendation and retention artifact seeding;
8. governed Codex implementation waves;
9. independent validation and bounded repair after major waves;
10. fresh generated-application capstone execution;
11. independent read-only architecture and security reviews;
12. a single local candidate commit whose parent is `5373b9bdd04ccd7760e65345d311362c5bc9a48f`;
13. post-commit proof that local main, origin/main and live remote main remain unchanged;
14. evidence sealing and exact governed stop marker.

Codex is given a guarded `git` executable that blocks all Git mutations. Only the V63 controller can create the branch and final candidate commit. Codex is also forbidden to add third-party dependencies, delete tracked files, push, merge, release, deploy or make certification claims.

## 12. Retention and cleanup safety

At campaign start V63 copies itself into:

```text
<state-root>/controller/run_upi_app_factory_phase71_82_enterprise_engineering_v63_standalone.sh
```

The retained copy may be used with `--resume <state-root>` even when the original Downloads copy is later moved or deleted.

V63 also generates a disabled-by-default cleanup script. Cleanup requires:

- a sealed successful campaign state;
- the explicit `--approved-after-closure` argument;
- a second typed confirmation;
- no automatic deletion of the candidate branch.

Do not clean the campaign state, worktree or retained controller before governed review and closure.

## 13. Required successful closure

Only a completely successful exact-candidate run may print:

```text
READY_FOR_GOVERNED_REVIEW
MERGE_PERFORMED=false
PUSH_PERFORMED=false
```

Failed or interrupted runs preserve the branch, worktree, state, controller, logs and evidence and print `FAILED_CLOSED` or `INTERRUPTED_PRESERVED`.

## 14. Preparation status

- Standalone controller prepared: **true**.
- Previous-controller dependency: **none**.
- Controller shell syntax validation: required and performed before delivery.
- Controller embedded benchmark validation: required and performed before delivery.
- User repository campaign execution: **not performed in this environment**.
- Feature branch created: **false**.
- Candidate commit created: **false**.
- Merge performed: **false**.
- Push performed: **false**.


## V63 controller corrections

V63 corrects the V62/V61 baseline-validation defect discovered on 2026-07-25. The immutable baseline's authoritative quality commands are `ruff check app factory tests`, `mypy app factory`, and full `pytest -q`; repository-wide `ruff check .` is not the declared baseline lint contract. V63 additionally isolates checksummed clean-clone hydration files from candidate scope and stages only explicit candidate paths.
