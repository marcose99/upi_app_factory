# Environment Specification

Recommended environment:
- Linux environment with Bash
- Python 3.10 or newer
- Git
- Local filesystem write access
- No live payment credentials required
- No OpenAI API key required for the default deterministic mock-safe route

Supported platform routes:
- Native Ubuntu/Linux for the Bash/Python local operator portal route.
- Docker/Compose on Linux Docker Engine.
- Docker/Compose on macOS Docker Desktop.
- Docker/Compose on Windows Docker Desktop.

Non-claims:
- Native Windows runtime support is not claimed.
- Native macOS runtime support is not claimed.
- Docker/Compose support is a local container route, not cross-platform native
  runtime proof.
- The posture remains `certification_ready_not_certified`.

Python capabilities:
- FastAPI
- Pydantic
- pytest
- ruff
- mypy

Runtime state:
- Default: `.var/upi_app_factory`
- Subdirectories: `runs`, `portfolio`, `runtime`, `logs`, `downloads`, `evidence`
- Override: `./run_factory.sh --state-root <path>` and `./stop_factory.sh --state-root <path>`
- The default state is repository-relative and ignored by Git; an explicit
  external override is permitted for recipient machines.

Network boundary:
- The generated application does not need live NPCI, RBI, bank, PSP, ODR,
  settlement, or payment-rail network access.
- Any such integration must remain blocked until a future explicitly approved
  live-integration phase, which is outside the current project boundary.

Data boundary:
- Do not use real customer data.
- Use synthetic/local test data only.

Factory portal Docker/Compose smoke path:
1. Run `docker compose up --build`.
2. Open `http://127.0.0.1:8036/health` and confirm the JSON health status is
   `ok`.
3. Open `http://127.0.0.1:8036/operator-ui/`.
4. Optionally set `UPI_APP_FACTORY_HOST_PORT=18036` before `docker compose up
   --build` to publish the same container port on a different loopback host
   port.
5. Run `docker compose down` for clean shutdown.

The Compose service publishes only to `127.0.0.1`, persists container state at
`/app/.var` through a named volume, runs with mock-only defaults, and keeps
runtime LLM calls disabled by default. No real NPCI, RBI, bank, PSP, ODR,
settlement, payment-rail, or provider calls are part of this route.

## Dependency reproducibility and supply-chain boundary

The native recipient route uses two governed exact locks:

- `requirements/bootstrap-lock.txt` pins the packaging toolchain used to create
  and maintain the local virtual environment.
- `requirements/recipient-lock.txt` pins the third-party dependency graph used
  for factory handover replay and generated-application validation.

`requirements-recipient.txt` is only the stable entry point that includes the
recipient lock and installs the first-party repository as editable source.
`run_factory.sh` binds its environment stamp to the bootstrap lock, recipient
entry file, recipient lock, and `pyproject.toml`, so a lock-only or packaging
metadata change cannot silently reuse a stale environment.

Known-vulnerability auditing remains a release/assurance activity. The editable
first-party `upi-app-factory` package is intentionally excluded from PyPI-backed
third-party vulnerability lookup; all locked third-party distributions remain
in scope for the audit.
