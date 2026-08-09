# Local and Docker Deployment

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Provide the authoritative local recipient and Docker/Compose routes and explicit boundaries.<br>
> **Audience:** recipients, operators, developers and reviewers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC 20000-1:2018 and SRE practices
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Native Linux recipient route

```bash
git clone <repository-url>
cd upi_app_factory
./run_factory.sh
```

Copy `<repository-url>` from GitHub's **Code** menu.

For browser-suppressed startup:

```bash
./run_factory.sh --no-browser
```

`run_factory.sh` creates/verifies `.venv`, installs from repository lock inputs when needed, rejects lock drift/unexpected distributions, runs `pip check`, asserts mock/no-real-payment/no-live-LLM safety and starts the health-gated portal. Do **not** replace this recipient route with `pip install -e ".[dev]"` as the handover procedure.

## Docker/Compose route

```bash
docker compose up --build
```

Optional host port:

```bash
UPI_APP_FACTORY_HOST_PORT=18036 docker compose up --build
```

Stop:

```bash
docker compose down
```

The Compose contract uses a read-only root filesystem, non-root UID/GID, loopback host publication, `/health` healthcheck, persistent `.var` volume and mock/payment/LLM safety variables.

This route is supported on **Linux Docker Engine** and may be exercised through **macOS Docker Desktop** or **Windows Docker Desktop** where Docker provides the container runtime. **Do not use this route as evidence of native Windows or native macOS support.**

## State and ports

- Native default state: `./.var/upi_app_factory`
- Docker state: named `.var` volume
- Native default host: `127.0.0.1`
- Native default port: `8036`
- Docker host publication: loopback only

Production ingress, TLS termination, HA, Kubernetes, production secret stores and live payment/provider connections are outside this local guide.
