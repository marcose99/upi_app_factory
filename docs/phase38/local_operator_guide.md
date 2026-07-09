# Phase 38 Local Operator Guide

This guide lets another operator run the local UPI dispute resolution factory from this checkout without enabling live ecosystem calls.

## Boundary

- Posture: `certification_ready_not_certified`.
- Scope: local-readiness for operator workflows only.
- No official certification, NPCI approval, RBI approval, bank approval, or legal approval is claimed.
- No live UPI, bank, NPCI, RBI, payment rail, upstream, downstream, or third-party integration is enabled.
- Do not create real credentials, deploy, merge, tag, or push as part of local operation.

## Quick Start

Run from repository root:

```bash
.venv/bin/python scripts/validate_phase38_portal_ux_polish_and_operator_guides.py
```

Expected output:

```text
Phase 38 portal UX polish and operator guides validated.
```

Run the focused test set:

```bash
.venv/bin/python -m pytest tests/test_phase38_portal_ux_polish_and_operator_guides.py
```

Expected output includes:

```text
passed
```

Start the local operator portal:

```bash
.venv/bin/python scripts/run_phase36_operator_portal_local_web_ui.py
```

Expected output is a local portal URL. Open only the local URL. The portal uses local files and mocked or simulated ecosystem boundaries.

## Safe Operating Sequence

1. Run the Phase 38 validator.
2. Start the local portal.
3. Use Health to confirm the local API process responds.
4. Use Evidence Dashboard to inspect local lifecycle artifacts.
5. Use Download Center to create a governed local export only when needed.
6. Use Validation dry-run before running validation.
7. Use Validation run with `phase34_runner_self_check` for the local self-check.
8. Use Latest report to inspect the most recent local validation result.

## Stop Conditions

Stop and inspect troubleshooting guidance if any portal panel returns `failed`, `missing`, `unavailable`, malformed report details, or a rejected validation command. Do not bypass these states with live providers or source-control actions.
