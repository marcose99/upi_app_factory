# UPI App Factory Logging Standard

> **Canonical observability context:** [Observability and SLO Boundaries](../operations/OBSERVABILITY_AND_SLOS.md). This logging standard defines implemented logging semantics; it does not claim a production metrics/alerting backend.

UPI App Factory emits dependency-light JSON logs to stdout by default. The
schema is OpenTelemetry Logs Data Model aligned, W3C Trace Context compatible,
and OWASP redaction oriented. It does not claim an external collector, SIEM,
production monitoring, regulatory approval, or formal certification.

Required envelope fields include `schema_version`,
`timestamp`, `observed_timestamp`, `severity_text`, `severity_number`, `body`,
`event_name`, `service.name`, `service.namespace`, `service.instance.id`,
`deployment.environment.name`, `source`, and correlation fields when available:
`trace_id`, `span_id`, `trace_flags`, `request_id`, and `correlation_id`.

HTTP request logs use `http.request.method`, `url.path`, and
`http.response.status_code`. Operation logs may include `run_id`, `app_id`,
`version_id`, `operation`, `outcome`, `duration_ms`, `error.type`, and a
bounded sanitized `error.message`.

Severity mapping follows OpenTelemetry ranges: DEBUG=5, INFO=9, WARNING=13,
ERROR=17, and CRITICAL=21.

Trace context accepts W3C `traceparent` version `00`; invalid or absent headers
receive cryptographically strong trace and span identifiers. Responses propagate
`traceparent` and `x-request-id`.

Redaction is recursive and covers keys containing authorization, cookie, token,
secret, password, api_key, credential, account, vpa, mobile, phone, email, pan,
aadhaar, card, cvv, payload, body, or content. CR/LF/control characters are
neutralized, field lengths are bounded, and arbitrary objects are not serialized
with `repr`.

Environment controls:

- `UPI_APP_FACTORY_LOG_LEVEL`
- `UPI_APP_FACTORY_LOG_FORMAT=json|console`
- `UPI_APP_FACTORY_LOG_FILE`
- `UPI_APP_FACTORY_LOG_MAX_BYTES`
- `UPI_APP_FACTORY_LOG_BACKUP_COUNT`
- `UPI_APP_FACTORY_LOG_INCLUDE_STACKTRACE=false`

Local file retention is owned by the operator who configured
`UPI_APP_FACTORY_LOG_FILE`; rotation is size based and local-only.

Example with fictional data:

```json
{"schema_version":"upi-app-factory.log.v1","timestamp":"2026-07-20T00:00:00.000Z","observed_timestamp":"2026-07-20T00:00:00.000Z","severity_text":"INFO","severity_number":9,"body":"Request completed.","event_name":"http.request.completed","service.name":"upi_demo_app","service.namespace":"upi_app_factory.engineered_applications","service.version":"v1_fictional","service.instance.id":"0123456789abcdef0123456789abcdef","deployment.environment.name":"local","trace_id":"11111111111111111111111111111111","span_id":"2222222222222222","trace_flags":"01","request_id":"fictional-request","http.request.method":"GET","url.path":"/health","http.response.status_code":200,"outcome":"success","source":"app.fictional.interfaces.api.main"}
```
