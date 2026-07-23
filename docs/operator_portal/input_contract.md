# Operator Portal Input Contract

Inputs are local-only operator fields and never trigger live payment providers.
Browser requirements normalize CRLF/CR to LF, reject empty or too-small input,
bound size to 128 KiB, and reject secret-like material. Approval token inputs
are password fields and are never persisted raw in run state, evidence, or logs.

Runtime inputs:

- Registered application/version selector maps to `app_id` and `version_id`.
- Runtime run ID defaults to `portfolio_runtime_001`.
- Runtime port is parsed as an integer and the backend validates 1024-65535.

Portfolio approval inputs map to actor, action, scope, approval token, and
nonce. Server-side nonce consumption remains authoritative and replay
protected.

Error behavior preserves safe user-entered values for correction while generic
browser-facing errors avoid tracebacks and internal absolute paths.

Sample requirements:

- The Use Sample Requirements control loads
  `examples/requirements/01_upi_failed_debit_no_credit.md` through
  `GET /operator-portal/api/requirements/sample`.
- The sample is local, deterministic, fictional, and mock-safe.
- This route does not replace paste/upload support; it only pre-fills the same
  governed intake field operators can edit before validation or submission.
