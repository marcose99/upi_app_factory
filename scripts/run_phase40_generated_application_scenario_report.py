#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_APP_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
APP_SOURCE = GENERATED_APP_ROOT / "app"
if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))

from upi_dispute_app.audit import AuditLogger  # noqa: E402
from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.repository import DisputeRepository  # noqa: E402
from upi_dispute_app.settings import RuntimeSettings  # noqa: E402


APP_ID = "upi_dispute_resolution"
PHASE = "phase40_generated_application_test_scenario_expansion"
CATALOG_PATH = (
    GENERATED_APP_ROOT / "tests/scenario_catalog/phase40_scenario_catalog.json"
)
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase40/"
    / "generated_application_scenario_report.json"
)
REQUIRED_CATEGORIES = {
    "positive",
    "negative",
    "edge",
    "contract",
    "replay",
    "audit",
    "resilience",
    "security",
    "performance-smoke",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def base_payload(suffix: str = "001") -> dict[str, object]:
    return {
        "client_request_id": f"phase40-req-{suffix}",
        "dispute_type": "duplicate_debit",
        "transaction_reference": f"PHASE40-TXN-{suffix}",
        "customer_upi_id": "phasecustomer@upi",
        "amount_paise": 50000,
        "description": "Customer reports duplicate debit for a local simulated transaction.",
        "evidence": {"customer_statement": "Duplicate debit visible in app screenshot."},
    }


async def request(
    app: Any,
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://local-generated-upi-dispute-app",
    ) as client:
        return await client.request(method, path, json=json_payload)


def make_app(tmpdir: Path) -> Any:
    settings = RuntimeSettings(
        app_env="test",
        data_dir=tmpdir,
        sqlite_path=tmpdir / "disputes.sqlite3",
        audit_log_path=tmpdir / "audit_events.jsonl",
    )
    return create_app(
        repository=DisputeRepository(settings.sqlite_path),
        audit_logger=AuditLogger(settings.audit_log_path),
        settings=settings,
    )


def pass_result(scenario: dict[str, Any], observed: dict[str, object]) -> dict[str, object]:
    return {
        "scenario_id": scenario["id"],
        "category": scenario["category"],
        "status": "passed",
        "expected_outputs": scenario["expected_outputs"],
        "observed_outputs": observed,
        "traceability": scenario["traceability"],
    }


def fail_result(
    scenario: dict[str, Any],
    observed: dict[str, object],
    message: str,
) -> dict[str, object]:
    return {
        "scenario_id": scenario["id"],
        "category": scenario["category"],
        "status": "failed",
        "expected_outputs": scenario["expected_outputs"],
        "observed_outputs": observed,
        "failure": message,
        "traceability": scenario["traceability"],
    }


def assert_equal(observed: object, expected: object, label: str) -> None:
    if observed != expected:
        raise AssertionError(f"{label}: expected {expected!r}, observed {observed!r}")


async def run_positive(app: Any) -> dict[str, object]:
    response = await request(app, "POST", "/disputes", json_payload=base_payload("positive"))
    body = response.json()
    dispute = body["dispute"]
    observed = {
        "status_code": response.status_code,
        "dispute_status": dispute["status"],
        "masked_customer_upi_id": dispute["masked_customer_upi_id"],
        "boundary_notice_contains": "mock/simulated" in body["boundary_notice"],
    }
    assert_equal(response.status_code, 201, "status_code")
    assert_equal(dispute["status"], "validation_pending", "dispute_status")
    assert_equal(dispute["masked_customer_upi_id"], "ph***r@upi", "masked_customer_upi_id")
    assert_equal(observed["boundary_notice_contains"], True, "boundary_notice_contains")
    return observed


async def run_negative(app: Any) -> dict[str, object]:
    response = await request(
        app,
        "POST",
        "/disputes",
        json_payload={**base_payload("negative"), "client_request_id": "bad request id"},
    )
    body = response.json()
    observed = {"status_code": response.status_code, "error_code": body["error"]["code"]}
    assert_equal(response.status_code, 422, "status_code")
    assert_equal(body["error"]["code"], "validation_error", "error_code")
    return observed


async def run_edge(app: Any) -> dict[str, object]:
    payload = {
        **base_payload("edge"),
        "dispute_type": "merchant_not_provided_service",
        "amount_paise": 2_000_000,
    }
    created = await request(app, "POST", "/disputes", json_payload=payload)
    dispute_id = created.json()["dispute"]["dispute_id"]
    checked = await request(app, "POST", f"/disputes/{dispute_id}/actions/mock-ecosystem-check")
    body = checked.json()
    observed = {
        "status_code": checked.status_code,
        "decision": body["decision"],
        "new_status": body["new_status"],
        "mock_sources_checked": body["mock_sources_checked"],
    }
    assert_equal(checked.status_code, 200, "status_code")
    assert_equal(body["decision"], "more_evidence_required", "decision")
    assert_equal(body["new_status"], "customer_action_required", "new_status")
    assert_equal(
        body["mock_sources_checked"],
        ["mock_bank_adapter", "mock_psp_adapter"],
        "mock_sources_checked",
    )
    return observed


async def run_contract(app: Any) -> dict[str, object]:
    health = await request(app, "GET", "/runtime/health")
    metrics = await request(app, "GET", "/runtime/metrics")
    health_body = health.json()["runtime_hardening"]
    metrics_body = metrics.json()
    observed = {
        "health_status_code": health.status_code,
        "metrics_status_code": metrics.status_code,
        "certification_boundary": health_body["certification_boundary"],
        "live_provider_calls_allowed": health_body["live_provider_calls_allowed"],
        "metrics_scope": metrics_body["observability_scope"],
    }
    assert_equal(health.status_code, 200, "health_status_code")
    assert_equal(metrics.status_code, 200, "metrics_status_code")
    assert_equal(
        health_body["certification_boundary"],
        "certification_ready_not_certified",
        "certification_boundary",
    )
    assert_equal(health_body["live_provider_calls_allowed"], False, "live_provider_calls_allowed")
    assert_equal(
        metrics_body["observability_scope"],
        "local_structured_runtime_counters_only",
        "metrics_scope",
    )
    return observed


async def run_replay(app: Any) -> dict[str, object]:
    payload = base_payload("replay")
    created = await request(app, "POST", "/disputes", json_payload=payload)
    replayed = await request(app, "POST", "/disputes", json_payload=payload)
    metrics = await request(app, "GET", "/runtime/metrics")
    created_id = created.json()["dispute"]["dispute_id"]
    replayed_id = replayed.json()["dispute"]["dispute_id"]
    observed = {
        "first_status_code": created.status_code,
        "replay_status_code": replayed.status_code,
        "same_dispute_id": created_id == replayed_id,
        "idempotency_replays": metrics.json()["metrics"]["idempotency_replays"],
    }
    assert_equal(created.status_code, 201, "first_status_code")
    assert_equal(replayed.status_code, 200, "replay_status_code")
    assert_equal(created_id == replayed_id, True, "same_dispute_id")
    assert_equal(metrics.json()["metrics"]["idempotency_replays"], 1, "idempotency_replays")
    return observed


async def run_audit(app: Any, tmpdir: Path) -> dict[str, object]:
    response = await request(app, "POST", "/disputes", json_payload=base_payload("audit"))
    assert_equal(response.status_code, 201, "status_code")
    audit_path = tmpdir / "audit_events.jsonl"
    entries = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    first = entries[0]
    details = first["details"]
    observed = {
        "audit_event_type": first["event_type"],
        "certification_boundary": details["certification_boundary"],
        "external_ecosystem_integrations": details["external_ecosystem_integrations"],
    }
    assert_equal(first["event_type"], "dispute_created", "audit_event_type")
    assert_equal(
        details["certification_boundary"],
        "certification_ready_not_certified",
        "certification_boundary",
    )
    assert_equal(
        details["external_ecosystem_integrations"],
        "mocked_or_simulated_only",
        "external_ecosystem_integrations",
    )
    return observed


async def run_resilience(app: Any) -> dict[str, object]:
    response = await request(app, "GET", "/disputes/disp_missing_phase40")
    body = response.json()
    observed = {
        "status_code": response.status_code,
        "error_code": body["error"]["code"],
        "boundary_notice_contains": "mock/simulated" in body["error"]["boundary_notice"],
    }
    assert_equal(response.status_code, 404, "status_code")
    assert_equal(body["error"]["code"], "http_error", "error_code")
    assert_equal(observed["boundary_notice_contains"], True, "boundary_notice_contains")
    return observed


async def run_security(app: Any) -> dict[str, object]:
    response = await request(
        app,
        "POST",
        "/disputes",
        json_payload={
            **base_payload("security"),
            "description": "Customer pasted long numeric sensitive value 123456789012.",
        },
    )
    body = response.json()
    observed = {
        "status_code": response.status_code,
        "error_code": body["error"]["code"],
        "message_contains": "long numeric sensitive data" in body["error"]["message"],
    }
    assert_equal(response.status_code, 422, "status_code")
    assert_equal(body["error"]["code"], "http_error", "error_code")
    assert_equal(observed["message_contains"], True, "message_contains")
    return observed


async def run_performance_smoke(app: Any) -> dict[str, object]:
    started = time.perf_counter()
    for index in range(10):
        response = await request(
            app,
            "POST",
            "/disputes",
            json_payload=base_payload(f"perf-{index:02d}"),
        )
        assert_equal(response.status_code, 201, f"status_code[{index}]")
    duration = time.perf_counter() - started
    metrics = await request(app, "GET", "/runtime/metrics")
    created_count = metrics.json()["metrics"]["disputes_created"]
    observed = {
        "created_count": 10,
        "duration_seconds": round(duration, 6),
        "disputes_created_metric": created_count,
        "max_duration_seconds": 2.0,
    }
    assert_equal(created_count, 10, "disputes_created_metric")
    if duration > 2.0:
        raise AssertionError(f"duration_seconds exceeded smoke threshold: {duration:.6f}")
    return observed


async def run_scenario(
    scenario: dict[str, Any],
    app: Any,
    tmpdir: Path,
) -> dict[str, object]:
    scenario_id = str(scenario["id"])
    try:
        if scenario_id == "positive_duplicate_debit_submission":
            observed = await run_positive(app)
        elif scenario_id == "negative_invalid_request_id":
            observed = await run_negative(app)
        elif scenario_id == "edge_high_value_more_evidence_path":
            observed = await run_edge(app)
        elif scenario_id == "contract_runtime_health_metrics":
            observed = await run_contract(app)
        elif scenario_id == "replay_idempotent_duplicate_submission":
            observed = await run_replay(app)
        elif scenario_id == "audit_local_boundary_metadata":
            observed = await run_audit(app, tmpdir)
        elif scenario_id == "resilience_missing_dispute_structured_error":
            observed = await run_resilience(app)
        elif scenario_id == "security_sensitive_numeric_description_rejected":
            observed = await run_security(app)
        elif scenario_id == "performance_smoke_bulk_local_submissions":
            observed = await run_performance_smoke(app)
        else:
            raise AssertionError(f"Unsupported scenario id: {scenario_id}")
    except Exception as exc:
        return fail_result(scenario, {}, str(exc))
    return pass_result(scenario, observed)


def validate_catalog(catalog: dict[str, Any]) -> None:
    scenarios = catalog.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Scenario catalog must contain scenarios")
    categories = {
        str(entry.get("category")) for entry in scenarios if isinstance(entry, dict)
    }
    if categories != REQUIRED_CATEGORIES:
        raise ValueError(f"Scenario categories mismatch: {sorted(categories)}")
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("Scenario entries must be objects")
        if not scenario.get("expected_outputs"):
            raise ValueError(f"Scenario missing expected outputs: {scenario.get('id')}")
        traceability = scenario.get("traceability")
        if not isinstance(traceability, list) or len(traceability) < 2:
            raise ValueError(f"Scenario missing traceability: {scenario.get('id')}")


async def build_report() -> dict[str, object]:
    catalog = load_json(CATALOG_PATH)
    validate_catalog(catalog)
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as parent_tmp:
        parent_tmpdir = Path(parent_tmp)
        scenario_results: list[dict[str, object]] = []
        for scenario in cast(list[dict[str, Any]], catalog["scenarios"]):
            tmpdir = parent_tmpdir / str(scenario["id"])
            tmpdir.mkdir()
            app = make_app(tmpdir)
            scenario_results.append(await run_scenario(scenario, app, tmpdir))
    passed = sum(1 for result in scenario_results if result["status"] == "passed")
    failed = len(scenario_results) - passed
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "status": "passed" if failed == 0 else "failed",
        "catalog": str(CATALOG_PATH.relative_to(PROJECT_ROOT)),
        "scenario_count": len(scenario_results),
        "passed_count": passed,
        "failed_count": failed,
        "categories_covered": sorted(REQUIRED_CATEGORIES),
        "scenario_results": scenario_results,
        "safety_boundaries": {
            "certification_boundary": "certification_ready_not_certified",
            "official_certification_claimed": False,
            "official_certification_granted": False,
            "production_readiness_claimed": False,
            "local_readiness_scope": "local_generated_application_scenario_validation_only",
            "live_provider_calls_allowed": False,
            "real_secrets_allowed": False,
            "deployment_allowed": False,
            "merge_allowed": False,
            "tag_allowed": False,
            "push_allowed": False,
            "external_ecosystem_integrations": "mocked_or_simulated_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = asyncio.run(build_report())
    if not args.no_write:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
