# Phase 38 Status Taxonomy

The portal uses explicit local statuses so operators do not infer success from missing evidence.

| Status | Operator meaning |
| --- | --- |
| `ok` | The local API process is responding. |
| `available` | A local artifact or report exists and can be read. |
| `missing` | A local artifact is absent; run the documented local command that creates it. |
| `configured` | A local command or workflow is known, but this phase did not execute it. |
| `unavailable` | The local command or workflow is not configured in this checkout. |
| `dry_run` | The validation runner listed approved commands without executing them. |
| `passed` | The local validation command completed with return code 0. |
| `failed` | The local validation command completed with a non-zero return code. |
| `skipped` | The workflow intentionally did not run that action. |
| `export_ready` | A governed local export bundle was created by the existing download center. |
| `error` | The portal could not complete the request; inspect the returned next steps. |

These statuses describe local operator workflows only. They do not certify the application, approve UPI participation, enable bank/NPCI/RBI/payment rail integrations, or authorize deployment.
