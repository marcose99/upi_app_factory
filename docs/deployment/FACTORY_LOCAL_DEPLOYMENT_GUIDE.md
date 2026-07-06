# Factory Local Deployment Guide

This deployment guide is for running the factory locally on a recipient machine.

## Deployment type

Local developer/operator deployment only.

## Steps

```bash
git clone <repo-url>
cd upi_dispute_resolution_factory
git checkout <validated-release-tag>
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Validate:

```bash
python scripts/validate_phase13c_agent_runtime_foundation.py
python scripts/validate_phase13c_self_correction_governance.py
python -m pytest -q
```

## Boundary

This is not production deployment.
This is not a live UPI/payment deployment.
