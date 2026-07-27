# Generated Application Local Deployment Guide

The generated application can be run locally:

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application
PYTHONPATH=.. python -m uvicorn generated_application.app.interfaces.api.main:app --reload
```

Test locally:

```bash
PYTHONPATH=.. python -m pytest -q app/tests
```

OpenAPI:

```text
http://127.0.0.1:8000/docs
```

External systems remain mock/simulated only.
