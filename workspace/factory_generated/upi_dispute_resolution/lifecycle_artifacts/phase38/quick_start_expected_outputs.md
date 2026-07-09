# Phase 38 Quick Start Expected Outputs

Run:

```bash
.venv/bin/python scripts/validate_phase38_portal_ux_polish_and_operator_guides.py
```

Expected:

```text
Phase 38 portal UX polish and operator guides validated.
```

Run:

```bash
.venv/bin/python -m pytest tests/test_phase38_portal_ux_polish_and_operator_guides.py
```

Expected output includes `passed`.

Run:

```bash
.venv/bin/python scripts/run_phase36_operator_portal_local_web_ui.py
```

Expected output is a local operator portal URL. The run remains local-only and keeps external ecosystem integrations mocked or simulated.
