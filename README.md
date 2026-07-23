# UPI App Factory

A lightweight, local-first, governed agentic software factory for generating a mock-safe UPI failed transaction and dispute resolution case management application.

License: Apache-2.0.

## Status

Local production-disciplined factory prototype.

Not NPCI certified. Not RBI certified. Not live-bank integrated. No real money movement.

Phase 45 consolidates the final v1.0 local candidate at the professional
stopping point. The posture remains `certification_ready_not_certified`.
Readiness language is limited to local-readiness evidence, and UPI rails, banks,
NPCI/RBI interfaces, payment rails, upstream/downstream systems, and third-party
services remain mocked or simulated.

Prepared future release label text:
`v1.0.0-local-governed-upi-factory-candidate`. Phase 45 does not create that
label, deploy, merge, push, create real secrets, call live providers, or claim
official certification.

Final candidate evidence starts at
`workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase45/final_evidence_index.json`.

## Start

Supported local runtime routes:
- Native Ubuntu/Linux with Bash and Python.
- Docker/Compose on Linux Docker Engine, macOS Docker Desktop, and Windows Docker Desktop.

Native Windows and native macOS execution are not claimed or validated. Use the Docker/Compose route on those hosts.

Native Ubuntu/Linux route:

```bash
./run_factory.sh --no-browser
```

The command creates or reuses `.venv`, installs/verifies
`requirements-recipient.txt`, initializes repository-relative state under
`.var/upi_app_factory`, starts the local operator portal, waits for `/health`,
and prints the verified `/operator-ui/` URL. The default route is deterministic,
mock-safe, and does not require an OpenAI API key.

Useful options:

```bash
./run_factory.sh --host 127.0.0.1 --port 0 --state-root .var/upi_app_factory --url-file .var/upi_app_factory/operator_url.txt --no-browser
./stop_factory.sh --state-root .var/upi_app_factory
```

Public hygiene validation:

```bash
make validate
make validate-public-clone
make run
```

Factory portal Docker/Compose route:

```bash
docker compose up --build
```

The portal is published on loopback only:

- http://127.0.0.1:8036/health
- http://127.0.0.1:8036/operator-ui/

Use a different host port when needed:

```bash
UPI_APP_FACTORY_HOST_PORT=18036 docker compose up --build
```

Clean shutdown:

```bash
docker compose down
```

The Docker route persists local portal state in the Compose-managed `/app/.var`
volume. It starts with `FACTORY_LLM_ENABLED=0`,
`UPI_APP_FACTORY_LLM_ENABLED=0`, `REAL_PAYMENT_CALLS=disabled`, and
`UPI_APP_FACTORY_REAL_PAYMENT_CALLS=disabled`; no secrets are baked into the
image. Do not use this route as evidence of native Windows or native macOS
support, production readiness, NPCI certification, RBI certification, or live
payment ecosystem integration.

Static Docker contract validation:

```bash
make validate-docker-platform
```

## URLs

- http://127.0.0.1:8036/health
- http://127.0.0.1:8036/operator-ui/

## Principles

- Deterministic local tools first; default runtime LLM calls are zero.
- Lightweight local tools first.
- Mock-safe regulated-domain simulation.
- Evidence-first claims.
- Validation before readiness.
- Human feedback as governed improvement loop.

## Public Clone Hygiene

This public clean-clone lane is licensed under Apache-2.0. See `LICENSE` and
`NOTICE`.

Tracked `workspace/` content is limited to deterministic public fixtures and
portable evidence. Runtime outputs are ignored and must be regenerated locally;
the governing policy is `policies/tracked_workspace_policy.json`.

Run the public hygiene gate with:

```bash
python scripts/validate_public_clone_readiness.py --repo . --license Apache-2.0
```
