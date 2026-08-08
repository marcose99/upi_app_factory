# API and Event Contracts

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Describe the semantically authoritative HTTP surface and event-contract ownership without counting test/tooling/history routes as product APIs.<br>
> **Audience:** API consumers, developers, architects, testers and reviewers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- OpenAPI Specification 3.2.0 reference model
- AsyncAPI Specification 3.1.0 where an event API is actually present

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Authoritative HTTP surface

Raw AST discovery found **312** route declarations. Semantic review classifies **167** as authoritative and collapses them to **123 unique HTTP method/path keys**. **145** declarations belong to tests, fixtures, tooling or historical/workspace material and are excluded.

## Route inventory

| Method/path | Surface | Source |
|---|---|---|
| `GET /` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/final_demo_app.py` |
| `GET /` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /app.js` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/final_demo_app.py` |
| `GET /capabilities` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /capabilities` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /cases` | AUTHORITATIVE_FACTORY_RUNTIME | `app/disputes/router.py` |
| `GET /cases` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/app/disputes/router.py` |
| `GET /cases` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/disputes/router.py` |
| `GET /cases/{case_id}` | AUTHORITATIVE_FACTORY_RUNTIME | `app/disputes/router.py` |
| `GET /cases/{case_id}` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/app/disputes/router.py` |
| `GET /cases/{case_id}` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/disputes/router.py` |
| `GET /catalogue` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `GET /disputes` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /disputes` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `GET /disputes` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /disputes` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `GET /disputes/{dispute_id}` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /disputes/{dispute_id}` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `GET /disputes/{dispute_id}` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /disputes/{dispute_id}` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `GET /downloads/recipient` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/capstone_phase69_api.py` |
| `GET /events` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/autonomous_campaign_api.py` |
| `GET /evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/capstone_phase69_api.py` |
| `GET /evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `GET /health` | AUTHORITATIVE_FACTORY_RUNTIME | `app/main.py` |
| `GET /health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `GET /health` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /health` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `GET /live` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /live` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /metrics` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /metrics` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /missing` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /missing` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /mock-failed-transactions` | AUTHORITATIVE_FACTORY_RUNTIME | `app/disputes/router.py` |
| `GET /mock-failed-transactions` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/app/disputes/router.py` |
| `GET /mock-failed-transactions` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/disputes/router.py` |
| `GET /operator-portal` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/final_demo_app.py` |
| `GET /operator-portal/api/debug-plan/factory` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/debug_plan_api.py` |
| `GET /operator-portal/api/debug-plan/factory/download` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/debug_plan_api.py` |
| `GET /operator-portal/api/deep-engineering/download/evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/deep-engineering/download/source` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/deep-engineering/evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/deep-engineering/overview` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/deep-engineering/source` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/documentation/factory` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/documentation_api.py` |
| `GET /operator-portal/api/documentation/factory/download` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/documentation_api.py` |
| `GET /operator-portal/api/requirements/sample` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}/downloads/application` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}/downloads/evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}/events` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}/evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}/native-pre-run/artifacts/{artifact}` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runs/{run_id}/validation` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/api/runtime-plane-authority` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-portal/deep-engineering` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /operator-portal/health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/final_demo_app.py` |
| `GET /operator-portal/health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /operator-ui/` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /operator-ui/app.js` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /operator-ui/runtime.css` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /operator-ui/runtime.js` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /operator-ui/styles.css` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /portal/download-center/status` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /portal/evidence-dashboard` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /portal/operator-guides` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /portal/token-economics` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /portal/validation-runner/dry-run` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /portal/validation-runner/latest-report` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `GET /portal/web-ui/manifest` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/web_ui/app.py` |
| `GET /ready` | AUTHORITATIVE_FACTORY_RUNTIME | `app/main.py` |
| `GET /ready` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /ready` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /reports/open-blockers` | AUTHORITATIVE_FACTORY_RUNTIME | `app/feedback/routes.py` |
| `GET /runs/{run_id}/downloads/evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/events` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/evidence` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/logs` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/metrics` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/openapi` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/status` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runs/{run_id}/view` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /runtime/diagnostics` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /runtime/diagnostics` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /runtime/health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /runtime/health` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `GET /runtime/health` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /runtime/health` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `GET /runtime/metrics` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `GET /runtime/metrics` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `GET /scenario-catalog` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `GET /source` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/capstone_phase69_api.py` |
| `GET /startup` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `GET /startup` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /status` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/autonomous_campaign_api.py` |
| `GET /status` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/capstone_phase69_api.py` |
| `GET /styles.css` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/final_demo_app.py` |
| `GET /v1/disputes` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /v1/disputes/{dispute_id}` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /v1/disputes/{dispute_id}/audit-integrity` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /v1/disputes/{dispute_id}/history` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /v1/disputes/{dispute_id}/timeline` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `GET /view` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/capstone_phase69_api.py` |
| `GET /view` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `GET /{feedback_id}` | AUTHORITATIVE_FACTORY_RUNTIME | `app/feedback/routes.py` |
| `POST /approvals` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /cases/from-failed-transaction` | AUTHORITATIVE_FACTORY_RUNTIME | `app/disputes/router.py` |
| `POST /cases/from-failed-transaction` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/app/disputes/router.py` |
| `POST /cases/from-failed-transaction` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/disputes/router.py` |
| `POST /cases/{case_id}/actions` | AUTHORITATIVE_FACTORY_RUNTIME | `app/disputes/router.py` |
| `POST /cases/{case_id}/actions` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/app/disputes/router.py` |
| `POST /cases/{case_id}/actions` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/disputes/router.py` |
| `POST /compare` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /demonstration` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/capstone_phase69_api.py` |
| `POST /disputes` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `POST /disputes` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `POST /disputes` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /disputes` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `POST /disputes/{dispute_id}/actions/mock-ecosystem-check` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/upi_dispute_app/main.py` |
| `POST /disputes/{dispute_id}/actions/mock-ecosystem-check` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/main.py` |
| `POST /drain` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `POST /drain` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /lifecycle` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /operator-portal/api/deep-engineering/approved-run` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/deep-engineering/compile` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/deep-engineering/proposal` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/factory-improvement/proposal` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/requirements/validate` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/runs` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/runs/{run_id}/approvals` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/runs/{run_id}/cancel` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/runs/{run_id}/execute` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /operator-portal/api/runs/{run_id}/plan` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /portal/download-center/export` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /portal/validation-runner/run` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/local_web_api.py` |
| `POST /runs/{run_id}/approvals` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `POST /runs/{run_id}/restart` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `POST /runs/{run_id}/scenarios` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `POST /runs/{run_id}/start` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `POST /runs/{run_id}/stop` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/runtime_api.py` |
| `POST /runtime/logs` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/metrics` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/openapi` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/restart` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/start` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/status` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/stop` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /runtime/stop-all` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /scenario/echo` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py` |
| `POST /scenario/echo` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /scenarios` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /scenarios/aggregate` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/portfolio_api.py` |
| `POST /v1/disputes` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/classify` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/close` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/disposition` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/evidence` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/human-review` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/investigate` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/investigation` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/quarantine` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/resolution` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /v1/disputes/{dispute_id}/review-decisions` | AUTHORITATIVE_GENERATED_APPLICATION | `workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py` |
| `POST /{action}` | AUTHORITATIVE_FACTORY_RUNTIME | `factory/operator_portal/autonomous_campaign_api.py` |

Duplicate declarations may represent compatibility aliases or implementation layering; the unique route key is the consumer-facing count.

## OpenAPI

OpenAPI exposed/generated by authoritative FastAPI applications is the machine-readable HTTP contract. This guide summarizes ownership/boundaries and does not replace generated schema.

## Event/message artifacts discovered

- `factory/templates/mock_dispute_app/generated_application/app/domain/domain_events.py`
- `factory/templates/mock_dispute_app/generated_application/app/tests/contract/test_event_contract.py`
- `factory/templates/mock_dispute_app/generated_application/asyncapi.yaml`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/app/domain/domain_events.py`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/contract/test_event_contract.py`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/app/upi_dispute_app/domain_events.py`
- `workspace/factory_generated/upi_dispute_resolution/generated_application/asyncapi.yaml`

AsyncAPI 3.1.0 is an applicability reference only when an actual event API warrants it. Absence of an AsyncAPI file is not repaired by inventing unsupported channels/messages.
