# Generated UPI Dispute Resolution Application

This is the authoritative generated source bundle at factory baseline `cdb9afab385cc0ada381d045a5509671bba617aa`. Payment ecosystems remain mock/simulated.

## Independent bootstrap

```bash
./scripts/bootstrap_cleanroom.sh
.venv/bin/python scripts/validate_dependency_contract.py
.venv/bin/python -m pytest -q app/tests
./scripts/start_local.sh
```

The bundle owns `requirements-bootstrap.lock`, `requirements.lock`, `dependency_contract.json`, `scripts/bootstrap_cleanroom.sh`, and `scripts/validate_dependency_contract.py`.

The current runtime entrypoint is `generated_application.app.interfaces.api.main:app`. `start_local.sh` prefers this application's own `.venv/bin/python`.

This is a locally runnable, independently reproducible source bundle. It does not claim production readiness. Wheel packaging, regulatory approval, certification, live payment operation and legal sufficiency are not claimed.

See the factory-level `docs/handover/GENERATED_APPLICATION_HANDOVER.md`.
