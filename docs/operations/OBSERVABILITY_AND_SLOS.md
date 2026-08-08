# Observability and SLO Boundaries

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Explain implemented telemetry, correlation and retention plus limits of current service-level claims.<br>
> **Audience:** operators, SRE/support engineers, developers, architects and security reviewers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- OpenTelemetry Semantic Conventions current reference
- ISO/IEC 20000-1:2018 and SRE practices

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Implemented telemetry

The repository logging standard defines structured JSON logging, OpenTelemetry-aligned field naming, W3C Trace Context compatibility, request/correlation identifiers, severity mapping and recursive redaction. See [Logging Standard](../observability/logging_standard.md).

## Logs, traces and correlation

Core logs carry timestamps, severity, event/body, service identity, deployment environment and source. HTTP/operation logs may include method/path/status, run/app/version IDs, operation/outcome/duration and bounded errors. W3C `traceparent`, trace/span identifiers, request IDs and correlation IDs provide correlation semantics without claiming an external tracing backend.

## Metrics

Metrics exposed by specific runtime components remain source-contract specific. This release does **not** claim a production metrics backend, external collector, enterprise dashboard or paging service.

## SLI/SLO boundary

The accepted local system has executable health/acceptance indicators but no production availability/latency SLO. Useful local acceptance indicators include health endpoint success, Governed CI success, full regression, runtime scenario/evidence completion and dependency closure consistency. They are not production SLAs.

## Alerting and dashboards

Local portal/evidence surfaces provide operational visibility. External alert routing or production dashboards are not claimed.

## Retention and privacy

Local file rotation/retention is operator-owned when configured. Redaction protects credentials and common payment/customer identifiers. Evidence must not contain real customer secrets.
