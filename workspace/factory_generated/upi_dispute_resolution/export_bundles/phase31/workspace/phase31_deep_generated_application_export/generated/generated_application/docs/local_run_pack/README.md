# Generated Application Local Run Pack

This pack lets a reviewer run the generated UPI dispute application locally with
mocked or simulated external ecosystem behavior only.

Scope:
- Local FastAPI runtime for review and smoke testing.
- Local SQLite files under `var/local_runtime`.
- Mocked or simulated UPI rails, banks, NPCI/RBI interfaces, payment rails,
  upstream/downstream systems, notifications, and third-party services.
- Certification posture remains `certification_ready_not_certified`.

Out of scope:
- Live provider calls.
- Real secrets or credentials.
- Deployment, merge, tag, push, release, or generated export bundle creation.
- Official certification, regulatory approval, broad production readiness, or
  live payment operation claims.

## Start

From the repository root:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/start_local.sh
```

The app listens on `127.0.0.1:8042` by default.

The current runnable target is
`generated_application.app.interfaces.api.main:app`. Legacy
`upi_dispute_app.main` imports remain generated compatibility facades only.

## Health Check

With the local server running:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/health_check.py
```

Expected result: `/health`, `/startup`, `/live`, `/ready`, and `/metrics` return
mock-only local runtime status.

## Smoke Test

Run the offline smoke test without starting a server:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/smoke_test.py
```

The smoke test exercises OpenAPI security metadata, local-token verification,
authenticated dispute creation/retrieval through the application service,
OpenMetrics output, and unauthenticated-principal rejection without network
calls.

## Reset Local Artifacts

Local runtime files are disposable and are not generated source artifacts:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/clean_local_artifacts.sh
```
