# Generated Application Local Run Pack

This pack lets a reviewer run the generated UPI dispute application locally with
mocked or simulated external ecosystem behavior only.

Scope:
- Local FastAPI runtime for review and smoke testing.
- Local SQLite and JSONL audit files under `var/local_runtime`.
- Mocked or simulated UPI rails, banks, NPCI/RBI interfaces, payment rails,
  upstream/downstream systems, notifications, and third-party services.
- Certification posture remains `certification_ready_not_certified`.

Out of scope:
- Live provider calls.
- Real secrets or credentials.
- Deployment, merge, tag, push, release, or generated export bundle creation.
- Official certification, regulatory approval, broad production readiness, or
  live payment capability claims.

## Prerequisites

Run from the repository root with the project virtual environment available:

```bash
/home/marcose/projects/upi_dispute_resolution_factory/.venv/bin/python --version
```

## Configure

The generated app includes `.env.example` with mock-only local defaults. To run
with explicit environment values:

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application
cp .env.example .env.local
```

Do not put real secrets in `.env.local`. The generated app rejects live provider
mode and real-secret mode.

## Start

From the repository root:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/start_local.sh
```

The app listens on `127.0.0.1:8042` by default. Override only local host/port
values when needed:

```bash
UPI_DISPUTE_LOCAL_PORT=8043 \
  workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/start_local.sh
```

## Health Check

With the local server running:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/health_check.py
```

Expected result: `/health`, `/runtime/health`, and `/runtime/metrics` return
mock-only local status payloads.

## Smoke Test

Run the offline smoke test without starting a server:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/smoke_test.py
```

The smoke test exercises health, dispute creation, retrieval, and a mocked
ecosystem check through FastAPI's in-process test client.

## Validate The Run Pack

From the repository root:

```bash
/home/marcose/projects/upi_dispute_resolution_factory/.venv/bin/python \
  scripts/validate_phase42_generated_application_local_run_pack.py
```

This checks required files, governance boundaries, local smoke behavior, and the
absence of enabled live providers, real secrets, release actions, or certification
claims.

## Reset Local Artifacts

Local runtime files are disposable and are not generated source artifacts:

```bash
workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/clean_local_artifacts.sh
```

The cleaner removes only known local runtime paths:
- `workspace/factory_generated/upi_dispute_resolution/generated_application/var/local_runtime`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/.pytest_cache`
- Python `__pycache__` directories under the generated app

It does not delete generated source, lifecycle artifacts, policies, prompts, tests,
or export bundle directories.
