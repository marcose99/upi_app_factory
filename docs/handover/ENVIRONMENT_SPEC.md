# Environment Specification

> **Status:** Canonical current-state documentation
> **Identity rule:** Environment and acceptance claims apply to the exact checked-out revision. Resolve it with `git rev-parse HEAD` and bind acceptance to Governed CI/evidence for that revision.

## Factory native route

Required:
- Linux environment with Bash
- Python 3.10 or newer, including the standard `venv` module and `pip`
- Git for cloning and exact-revision identity checks
- local filesystem write access to the clone and selected state directory
- either package-source access to every exact locked dependency or an already
  installed, verified compatible environment containing that exact closure

```bash
./run_factory.sh
```

The recipient environment is governed by `requirements/bootstrap-lock.txt`, `requirements/recipient-lock.txt`, `requirements-recipient.txt`, and `pyproject.toml`.

The launcher can verify and reuse a compatible environment, but it cannot obtain
missing packages while offline. For an offline native run, prepare all locked
artifacts in a local cache/wheelhouse or provide the verified exact environment
before starting. No dependency bundle is implied by the source clone.

## Generated-application clean-room route

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application
./scripts/bootstrap_cleanroom.sh
.venv/bin/python scripts/validate_dependency_contract.py
.venv/bin/python -m pytest -q app/tests
```

The generated application owns `requirements-bootstrap.lock`, `requirements.lock`, `dependency_contract.json`, and its clean-room bootstrap. The bootstrap verifies exact installed closure and runs `pip check`.

This route has the same offline limit: all exact generated-application pins must
already be available locally or installed in the environment being verified.

## Docker/Compose route

Docker with Compose is the existing alternative when the native Python
prerequisites are unavailable. Image construction may still require dependency
source access unless the required layers/artifacts are already cached locally.

Supported Docker host routes:
- Linux Docker Engine
- macOS Docker Desktop
- Windows Docker Desktop

```bash
docker compose up --build
```

The service publishes only to loopback. To select another loopback host port, set `UPI_APP_FACTORY_HOST_PORT`.

```bash
UPI_APP_FACTORY_HOST_PORT=18036 docker compose up --build
```

Stop with:

```bash
docker compose down --volumes --remove-orphans
```

## Supported claims and non-claims

Native Ubuntu/Linux and Docker/Compose routes are supported as documented by `config/supported_platforms.yaml`.

Do not use this route as evidence of native Windows or native macOS support.

Native Windows/macOS parity, wheel packaging, production deployment, certification and real-payment integration are not claimed.

## Safety

No live NPCI/RBI/bank/PSP/payment-rail access or real customer data is required. Default live LLM/provider use remains separately gated.

See [Supply Chain and Dependencies](../security/SUPPLY_CHAIN_AND_DEPENDENCIES.md) and [Generated Application Handover](GENERATED_APPLICATION_HANDOVER.md).
