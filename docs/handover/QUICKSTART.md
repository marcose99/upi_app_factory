# Quickstart for a New Machine

## 1. Clone and select release

```bash
git clone <repo-url>
cd upi_dispute_resolution_factory
git checkout <validated-release-tag>
```

## 2. Create Python environment

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If editable install is not configured yet, use the repository's current
dependency installation guidance in the root README or pyproject.

## 3. Validate baseline

```bash
python scripts/validate_phase13c_agent_runtime_foundation.py
python scripts/validate_phase13c_self_correction_governance.py
python scripts/validate_phase13b_generated_application.py
python scripts/validate_phase13b_progress_portal_observability.py
python -m pytest -q
```

## 4. Open portals

```text
workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_generation_progress_portal.html
workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_agent_runtime_portal.html
workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_self_correction_portal.html
```
