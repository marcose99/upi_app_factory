# Runtime Lifecycle Runbook

Scope: local mock/simulated runtime only.

## Startup

Start the FastAPI application with the local runner. Startup applies SQLite
migrations and sets startup, liveness and readiness true. Check `/startup`,
`/live`, `/ready` and `/runtime/diagnostics`.

The SQLite state path is explicit and local-first. Set
`UPI_DISPUTE_SQLITE_PATH` to place state under an operator-owned local directory;
the default is `state/local_disputes.sqlite3` relative to the process working
directory. Use one writable state path per local runtime process. Do not point
multiple simultaneously running processes at the same SQLite file.

## Drain And Shutdown

Call `POST /drain` before local shutdown with a signed local bearer principal
that has `runtime:drain` scope or the local `ops_admin` role. Readiness turns
false and ordinary application traffic receives 503 while liveness remains true.
Shutdown turns readiness and liveness false and records shutdown diagnostics.

## Dependency Health

Use `/ready` or authenticated `/runtime/diagnostics` with
`runtime:diagnostics` scope or the local `ops_admin` role. Dependencies are
local SQLite and `MOCK_BOUNDARY` adapters only. Live bank, PSP, NPCI, RBI,
identity-provider and payment-rail calls are not allowed.

## Rollback

For a failed local generated-app change, stop the local process, restore the
previous generated artifact bundle selected by the controller, and rerun the
fresh generation validator. Git, tags, releases and deployments are controlled
outside this generated runbook.

## Failure Modes

- SQLite migration drift: readiness returns degraded; repair migration ledger
  evidence before accepting new generated output.
- Drain left enabled: restart the local process or re-run startup.
- Trace header invalid: runtime creates a new valid W3C trace context and
  continues without rejecting the request.
- Metrics consumer unavailable: `/metrics` remains local text output; no
  Prometheus server or collector is required.
