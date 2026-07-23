# Operator Portal Debug Plan

The operator portal exposes the source-derived factory debug plan through:

- `GET /operator-portal/api/debug-plan/factory`
- `GET /operator-portal/api/debug-plan/factory/download`

The browser UI includes visible `view-factory-debug-plan` and
`download-factory-debug-plan` controls. The JSON response is hash-bound by
`plan_sha256`; the download endpoint returns the same JSON bytes as an
attachment.
