# ADR-0067: Repository-Owned Autonomous Control Plane

## Context

UPI App Factory already has lifecycle orchestration, autonomous supervision, governed repairs, run resolution, incident replay, operator portal controls, and evidence surfaces. Future work needs a durable repository-owned control plane that accepts declarative campaign manifests instead of manually applying route scripts.

The bootstrap must remain local-first and deterministic-first. External payment ecosystems are mocked or simulated only. The control plane is certification-ready-not-certified and does not authorize production deployment, public release, real payment rail access, customer data access, tags, releases, or certification statements.

## Decision

Add `tools/factory_control_plane` as a dependency-light Python standard-library implementation backed by SQLite. SQLite is configured with WAL journal mode, foreign keys, and FULL synchronous durability. Campaigns are stored as append-only hash-addressed events with tables for campaigns, activities and idempotency, policy decisions, approvals, incidents, and artifacts.

Campaign input is a schema version 1 JSON manifest with metadata, baseline, objective, scope, budgets, approvals, and activities. Activities declare action, risk, argv, dependencies, target state, timeout, cwd, environment allowlist, and allowed write paths. The loader fails closed on unknown fields, duplicate ids, unknown dependencies, cycles, path escapes, invalid budgets, and non-monotonic target states.

Manifests may also declare validation controls: trusted prerequisites and
deterministic runtime noise. The execution order is:

```text
reconcile -> hydrate -> baseline observe -> candidate observe -> classify -> repair only when attributable -> revalidate -> seal
```

The controller reconciles deterministic runtime noise before enforcing candidate
scope, hydrates only declared trusted prerequisites, observes baseline and
candidate validation results, classifies the failure, and reserves repair budget
only for a candidate-attributable `PRODUCT_DEFECT`. Identical baseline and
candidate validation failures are `BASELINE_DEFECT` and do not trigger repair.
The required classification vocabulary is `PRODUCT_DEFECT`, `TEST_DEFECT`,
`MISSING_PREREQUISITE`, `NON_HERMETIC_TEST`,
`DETERMINISTIC_RUNTIME_NOISE`, `BASELINE_DEFECT`, `CONTROLLER_DEFECT`,
`POLICY_DENIAL`, and `EVIDENCE_INTEGRITY_FAILURE`.

The lifecycle is monotonic and ordered from `NEW` through `CLOSED`. Backward transitions are structurally rejected, and `CLOSED` is terminal. Failures create incidents and do not roll back successful lifecycle state.

Execution and evidence verification are separate activity kinds. Verification activities may inspect existing artifacts, identities, and hashes, but may not declare write paths or trigger the operation being verified.

Policy is a deterministic standing charter in `config/control_plane/standing_policy.json`. It defaults to deny, automatically allows known actions through `MODERATE` risk, pauses for human-required actions, and denies prohibited or unknown actions. Policy decision ids are content-derived from action, risk, outcome, and policy digest.

## Alternatives

Temporal, OPA, Sigstore, and hosted policy or attestation services were deferred. They add operational weight and live integration boundaries that are not required for this bootstrap. Their contracts are modeled through backend-neutral local interfaces and JSON evidence formats so they can be introduced later without changing campaign semantics.

Manual route scripts were rejected as the future operating model because they do not provide durable state, idempotent replay, policy evidence before every activity, or operator inbox integration.

## Consequences

The control plane can run and resume local campaigns deterministically with durable idempotency. Completed activities with identical inputs are reused; changed inputs for an existing activity fail closed. Every transition, decision, reconciliation, hydration, observation, and classification emits hash-addressed or sealed evidence.

Existing lifecycle and supervisor systems remain the source of their own business logic. The new adapters reference their public entry points and contracts without copying implementation. Historical closed phases are represented by closure attestations and are not regenerated merely because a later campaign runs.

The first backend is local SQLite. A later Temporal coordinator can reuse the manifest, policy, lifecycle, activity result, failure classification, and evidence contracts while replacing only scheduling and persistence adapters.
