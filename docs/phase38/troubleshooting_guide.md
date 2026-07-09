# Phase 38 Troubleshooting Guide

Use this guide for local operator portal failures. Keep the posture `certification_ready_not_certified` while troubleshooting.

## Common States

`missing`: A local artifact was not found. Run the validator or safe self-check that creates the artifact.

`unavailable`: A local command is not configured in this checkout. Treat this as a configuration gap, not as success.

`failed`: A local command returned a non-zero exit code. Inspect `command_results`, stdout, and stderr in the report.

`rejected`: The portal blocked a request, usually because command IDs were not allowlisted. Run dry-run and use an approved ID.

`skipped`: The workflow intentionally did not run an action. This is common for generation commands in portal status views.

## Recovery Steps

For a rejected validation command:

```bash
.venv/bin/python scripts/validate_phase34_operator_portal_validation_runner.py
```

Expected output:

```text
Phase 34 operator portal validation runner validated.
```

For missing download metadata:

```bash
.venv/bin/python scripts/validate_phase32_operator_portal_download_center.py
```

Expected output:

```text
Phase 32 operator portal download center validated.
```

For stale or malformed latest validation report:

```bash
.venv/bin/python -m pytest tests/test_phase34_operator_portal_validation_runner.py
```

Expected output includes:

```text
passed
```

## Prohibited Recovery Paths

Do not use live providers, real credentials, deployment commands, merge commands, tag commands, or push commands to recover a local portal issue. External ecosystem integrations remain mocked or simulated.
