# Environment Specification

Current public baseline: `cdb9afab385cc0ada381d045a5509671bba617aa`.

## Factory native route

Required:
- Linux environment with Bash
- Python 3.10
- Git
- local filesystem write access

```bash
./run_factory.sh
```

The recipient environment is governed by `requirements/bootstrap-lock.txt`, `requirements/recipient-lock.txt`, `requirements-recipient.txt`, and `pyproject.toml`.

## Generated-application clean-room route

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application
./scripts/bootstrap_cleanroom.sh
.venv/bin/python scripts/validate_dependency_contract.py
.venv/bin/python -m pytest -q app/tests
```

The generated application owns `requirements-bootstrap.lock`, `requirements.lock`, `dependency_contract.json`, and its clean-room bootstrap. The bootstrap verifies exact installed closure and runs `pip check`.

## Docker/Compose route

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
