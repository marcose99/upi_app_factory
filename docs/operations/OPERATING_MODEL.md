# Operating Model

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Describe supported local startup, health, state, shutdown, runtime control, failure handling and escalation.<br>
> **Audience:** operators, recipients, developers and SRE/support engineers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC 20000-1:2018 and SRE practices
- ISO/IEC/IEEE 26514:2022
- OpenTelemetry Semantic Conventions current reference

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Native recipient route

```bash
./run_factory.sh
```

For browser-suppressed startup:

```bash
./run_factory.sh --no-browser
```

The launcher creates/verifies `.venv`, exact dependency closure, local state directories, mock/payment/LLM safety controls, starts through `start_factory.sh`, waits for health and prints the verified operator URL. Native hosts are restricted to `127.0.0.1` or `localhost`; `--port 0` may auto-select a port.

## Docker/Compose route

```bash
docker compose up --build
```

Stop:

```bash
docker compose down
```

Host port may be overridden with `UPI_APP_FACTORY_HOST_PORT`.

## Health and state

- Factory health: `GET /health`
- Canonical operator UI: `/operator-ui/`
- Native default state root: `./.var/upi_app_factory`
- State categories include runs, portfolio, runtime, logs, downloads and evidence.
- Docker persists `.var` through a named volume.

## Runtime lifecycle

The portal exposes guarded portfolio/runtime start, restart, stop and stop-all actions. Those controls are distinct from stopping the factory portal process/container.

## Native factory shutdown

If the revision has no dedicated repository-owned stop script, use the launcher/process supervisor or owning terminal/session. Do not kill unrelated Python processes by pattern. Docker shutdown remains `docker compose down`.

## Escalation

Escalate when a failure requires product semantic change, new dependency/provider capability, weakening a security/test/governance control, enabling live payment/LLM behavior or crossing a protected Git/release boundary.
