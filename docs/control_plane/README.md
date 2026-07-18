# UPI App Factory Control Plane

## Architecture

The autonomous control plane accepts declarative JSON campaign manifests and drives them through a durable monotonic lifecycle. It is local-first, deterministic-first, and standard-library only. The local backend is SQLite with WAL, foreign keys, and FULL synchronous durability.

The main package is `tools/factory_control_plane`. The repository command is:

```bash
bin/upi-app-factory-control-plane
```

The control plane converges existing repository assets through adapters:

- `bin/upi-app-factory-lifecycle` and `tools.lifecycle_orchestrator` remain the lifecycle implementation boundary.
- `tools.autonomous_supervisor` remains the autonomous supervisor boundary.
- Historical closed phases are referenced by closure attestations and are never automatically regenerated because a later campaign is running.

## Commands

```bash
bin/upi-app-factory-control-plane validate MANIFEST
bin/upi-app-factory-control-plane run MANIFEST
bin/upi-app-factory-control-plane resume MANIFEST
bin/upi-app-factory-control-plane status CAMPAIGN_ID
bin/upi-app-factory-control-plane policy-explain ACTION RISK
bin/upi-app-factory-control-plane seal-evidence CAMPAIGN_ID
bin/upi-app-factory-control-plane worker --once
bin/upi-app-factory-control-plane worker
```

Use `--state-root PATH` to place durable state in an isolated directory. Without it, state resolves from `UPI_APP_FACTORY_CONTROL_PLANE_STATE`, `XDG_STATE_HOME`, or a local `.control_plane_state` fallback.

## State And Evidence

Campaign execution order is fixed:

```text
reconcile -> hydrate -> baseline observe -> candidate observe -> classify -> repair only when attributable -> revalidate -> seal
```

`validation_controls` in the manifest declaratively lists trusted validation
prerequisites and deterministic runtime noise. Runtime noise is reconciled
before candidate scope is enforced. Trusted prerequisites are hydrated only when
explicitly declared as hydratable; otherwise missing prerequisites fail closed as
`MISSING_PREREQUISITE` before any repair agent could be invoked.

Verification activities are observed against the declared baseline reference and
the candidate worktree before classification. An identical baseline and
candidate failure is `BASELINE_DEFECT` and does not consume product-repair
budget. Only a candidate-attributable `PRODUCT_DEFECT` is eligible to consume
repair budget. Structured reconcile, hydrate, observation, classification, and
execution-order envelopes are written under campaign evidence.

State database:

```text
STATE_ROOT/control_plane.sqlite3
```

Evidence:

```text
STATE_ROOT/evidence/CAMPAIGN_ID/
STATE_ROOT/sealed/
```

Every state transition and policy decision emits a hash-addressed event. Activity envelopes capture argv-list execution results, separated stdout and stderr, and SHA-256 hashes. Evidence sealing rejects symlinks, writes a JSON manifest, creates a tar.gz archive, and writes a checksum sidecar.

## Policy Boundary

`config/control_plane/standing_policy.json` is default deny. Known actions through `MODERATE` risk are automatic. Production deployment, public release, tag creation, real payment rail access, real customer data access, policy exceptions, destructive migrations, and certification statements require a human gate. Force-push to main, bypassing checks, disabling governance, committing secrets, deleting evidence, and live payment transactions are prohibited.

This repository surface is certification-ready-not-certified. It is local/mock only and does not authorize production deployment, release, certification, customer-data access, or real payment activity.

## Incident Handling

Failures create incident evidence and do not roll back the successful lifecycle
state. Failure classes are typed as `PRODUCT_DEFECT`, `TEST_DEFECT`,
`MISSING_PREREQUISITE`, `NON_HERMETIC_TEST`,
`DETERMINISTIC_RUNTIME_NOISE`, `BASELINE_DEFECT`, `CONTROLLER_DEFECT`,
`POLICY_DENIAL`, and `EVIDENCE_INTEGRITY_FAILURE`. Only
`PRODUCT_DEFECT` consumes engineering repair budget.

## Inbox Worker

The worker uses:

```text
STATE_ROOT/inbox/pending
STATE_ROOT/inbox/processing
STATE_ROOT/inbox/completed
STATE_ROOT/inbox/failed
```

Manifests are atomically moved from pending to processing. Successful results move to completed with a result sidecar. Failures move to failed with a result sidecar, preserving the original manifest for operator-portal triage.

## Future Temporal Backend

Temporal is intentionally not a bootstrap dependency. A later backend can implement the same manifest, lifecycle, policy, activity-result, incident, and evidence contracts while delegating scheduling and retry semantics to Temporal.
