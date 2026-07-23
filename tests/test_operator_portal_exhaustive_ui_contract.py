from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from factory.operator_portal.browser_intake_orchestration import APPROVAL_TOKEN
from factory.operator_portal.browser_intake_orchestration import BrowserIntakeOrchestrator
from factory.operator_portal.web_ui.app import create_web_ui_app
from scripts.build_operator_portal_exhaustive_ui_manifest import (
    GAP_KEYS,
    REQUIRED_APP_ID,
    SCHEMA_VERSION,
    build_manifest,
)
from tests.test_portal_page_workflow_e2e import run_portal_vm_scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_exhaustive_ui_manifest_cli_matches_required_schema(tmp_path: Path) -> None:
    output = tmp_path / "operator_portal_exhaustive_ui_manifest.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/build_operator_portal_exhaustive_ui_manifest.py"),
            "--project-root",
            str(PROJECT_ROOT),
            "--output",
            str(output),
        ],
        cwd=Path("/tmp"),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    manifest = json.loads(output.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["status"] == "PASS"
    assert manifest["live_http_e2e"] == {
        "required": True,
        "evidence_test": "tests/test_operator_portal_live_http_e2e.py",
        "loopback_http_process": True,
        "runtime_llm_calls_expected": 0,
        "real_payments_enabled": False,
    }
    assert set(manifest["gaps"]) == set(GAP_KEYS)
    assert all(value == [] for value in manifest["gaps"].values())
    assert manifest["summary"] == {
        "pages": 1,
        "inputs": 7,
        "controls": 37,
        "forms": 0,
        "routes": 36,
    }
    assert {item["id"] for item in manifest["inputs"]} == {
        "requirements-input",
        "app-id-input",
        "approval-actor",
        "approval-token",
        "runtime-version-selector",
        "runtime-run-id",
        "runtime-port-input",
    } - {"runtime-version-selector"} | {"runtime-version-selector"}
    assert all(item["evidence_tests"] and item["executed_behaviors"] for item in manifest["inputs"])
    assert all(item["evidence_tests"] and item["executed_behaviors"] for item in manifest["controls"])


def test_manifest_routes_match_fastapi_openapi_without_duplicate_operation_ids() -> None:
    manifest = build_manifest(PROJECT_ROOT)
    app = create_web_ui_app(project_root=PROJECT_ROOT)
    schema = app.openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))

    openapi_pairs = {
        f"{method.upper()} {path}"
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }
    for route in manifest["routes"]:
        path = str(route["route"])
        if "{run_id}" in path:
            path = path.replace("{run_id}", "{run_id}")
        assert f"{route['method']} {path}" in openapi_pairs


def test_all_portal_actions_issue_expected_routes_once_and_restore_busy_state() -> None:
    run_portal_vm_scenario(
        """
test.elements.get("requirements-input").value = "Failed debit with no beneficiary credit. ".repeat(4);
test.elements.get("app-id-input").value = "upi_failed_debit_no_credit";
test.elements.get("approval-actor").value = "operator";
test.elements.get("approval-token").value = "APPROVE_PORTAL_APPLICATION_ENGINEERING";
test.elements.get("runtime-run-id").value = "runtime_contract_run";
test.elements.get("runtime-port-input").value = "19042";
test.setRoute("GET /portal/validation-runner/dry-run", { status: "dry_run", report: { command_results: [{ id: "phase34_runner_self_check" }] } });
test.setRoute("POST /portal/validation-runner/run", { status: "passed", report: { command_results: [] } });
test.setRoute("GET /portal/validation-runner/latest-report", { status: "available", report: {} });
test.setRoute("GET /operator-portal/api/debug-plan/factory", { schema_version: "upi-app-factory.debug-plan.v1", routes: [{ method: "GET", path: "/health" }], plan_sha256: "a".repeat(64) });
test.setRoute("GET /operator-portal/api/documentation/factory", "<!doctype html><title>UPI App Factory Complete Guide</title>");
test.setRoute("POST /portal/download-center/export", { status: "export_ready", export: { bundle_path: "/tmp/local.zip" } });
test.setRoute("POST /operator-portal/api/requirements/validate", { status: "validated", validation: { sha256: "sha" } });
test.setRoute("POST /operator-portal/api/runs", {
  status: "run_created",
  run_id: "run_contract",
  run: { run_id: "run_contract", app_id: "upi_failed_debit_no_credit", state: "REQUIREMENTS_ACCEPTED", requirements_sha256: "sha", approval: null, updated_at_utc: "now", events: [] },
});
test.setRoute("POST /operator-portal/api/runs/run_contract/plan", {
  status: "plan_ready",
  run: { run_id: "run_contract", app_id: "upi_failed_debit_no_credit", state: "AWAITING_APPROVAL", requirements_sha256: "sha", approval: null, updated_at_utc: "now", events: [] },
});
test.setRoute("POST /operator-portal/api/runs/run_contract/approvals", {
  status: "approved",
  run: { run_id: "run_contract", app_id: "upi_failed_debit_no_credit", state: "APPROVED", requirements_sha256: "sha", approval: true, updated_at_utc: "now", events: [] },
});
test.setRoute("POST /operator-portal/api/runs/run_contract/execute", {
  status: "queued",
  run: { run_id: "run_contract", app_id: "upi_failed_debit_no_credit", state: "SUCCEEDED", requirements_sha256: "sha", approval: true, updated_at_utc: "now", final_decision: "GO", artifacts: { generated_application_available: true }, events: [] },
});
test.setRoute("GET /operator-portal/api/runs/run_contract", {
  run_id: "run_contract", app_id: "upi_failed_debit_no_credit", state: "SUCCEEDED", requirements_sha256: "sha", approval: true, updated_at_utc: "now", final_decision: "GO", artifacts: { generated_application_available: true }, events: [],
});
test.setRoute("POST /operator-portal/api/runs/run_contract/cancel", {
  status: "cancelled",
  run: { run_id: "run_contract", app_id: "upi_failed_debit_no_credit", state: "CANCELLED", requirements_sha256: "sha", approval: true, updated_at_utc: "now", events: [] },
});
test.setRoute("GET /operator-portal/api/runs/run_contract/validation", { state: "SUCCEEDED", decision: "GO" });
test.setRoute("GET /operator-portal/api/runs/run_contract/events", { events: [{ event: "done" }] });
test.setRoute("GET /operator-portal/api/runs/run_contract/evidence", { status: "available" });
test.setRoute("POST /operator-portal/api/portfolio/approvals", () => ({ status: "approved", nonce: "nonce_12345678" }));
for (const route of [
  "POST /operator-portal/api/portfolio/runtime/start",
  "POST /operator-portal/api/portfolio/runtime/restart",
  "POST /operator-portal/api/portfolio/runtime/stop",
  "POST /operator-portal/api/portfolio/runtime/openapi",
  "POST /operator-portal/api/portfolio/scenarios",
  "POST /operator-portal/api/portfolio/runtime/logs",
  "POST /operator-portal/api/portfolio/runtime/metrics",
]) {
  test.setRoute(route, { state: "READY", binding: { port: 19042 }, health: { status: "ok" }, mock_safe_local: true });
}
test.setRoute("POST /operator-portal/api/portfolio/runtime/stop-all?approval_nonce=nonce_12345678", { status: "stopped", stopped: [] });
test.setRoute("GET /operator-portal/api/portfolio/evidence", { status: "available", evidence: [] });

const actions = [
  "refresh-health", "refresh-evidence", "refresh-download", "refresh-guides",
  "validation-dry-run", "validation-run", "latest-report", "view-factory-debug-plan",
  "view-factory-documentation", "export-download",
  "use-sample-requirements", "validate-requirements", "submit-run", "generate-plan", "approve-engineering",
  "start-engineering", "refresh-run", "view-validation-report", "view-evidence",
  "runtime-approve-start", "runtime-start", "runtime-openapi", "runtime-scenarios",
  "runtime-logs", "runtime-metrics",
  "runtime-approve-restart", "runtime-restart", "runtime-approve-stop", "runtime-stop",
  "runtime-approve-stop-all", "runtime-stop-all", "runtime-evidence",
];
for (const action of actions) {
  const button = test.button(action);
  const original = button.textContent;
  await button.userClick();
  test.assert.strictEqual(button.getAttribute("aria-busy"), null, action);
  test.assert.strictEqual(button.textContent, original, action);
}
const counts = new Map();
for (const request of test.requests) {
  if (request.method === "POST") {
    counts.set(request.path, (counts.get(request.path) || 0) + 1);
  }
}
test.assert.strictEqual(counts.get("/operator-portal/api/runs"), 1);
test.assert.strictEqual(counts.get("/operator-portal/api/runs/run_contract/execute"), 1);
test.assert.strictEqual(test.link("download-application").getAttribute("aria-disabled"), "false");
test.assert.strictEqual(test.link("download-evidence").getAttribute("aria-disabled"), "false");
await test.button("cancel-run").userClick();
const cancelRequest = test.requests.find(
  (item) => item.path === "/operator-portal/api/runs/run_contract/cancel",
);
test.assert.strictEqual(cancelRequest.method, "POST");
console.log(JSON.stringify({ actions: actions.length, mutationRoutes: counts.size }));
"""
    )


def test_client_and_server_validation_parity_for_boundaries(tmp_path: Path) -> None:
    browser_orchestrator = BrowserIntakeOrchestrator(
        project_root=PROJECT_ROOT,
        state_root=tmp_path / "runs",
        portfolio_state_root=PROJECT_ROOT / "workspace/factory_generated/upi_failed_debit_no_credit/contract_portfolio" / tmp_path.name,
    )
    app = create_web_ui_app(
        project_root=PROJECT_ROOT,
        browser_orchestrator=browser_orchestrator,
        runtime_state_root=tmp_path / "runtime",
        portfolio_state_root=PROJECT_ROOT / "workspace/factory_generated/upi_failed_debit_no_credit/contract_portfolio" / tmp_path.name,
    )
    client = TestClient(app)
    valid_requirements = "Failed debit and no beneficiary credit workflow. " * 3

    valid = client.post(
        "/operator-portal/api/requirements/validate",
        json={"requirements": valid_requirements.replace("\n", "\r\n"), "app_id": REQUIRED_APP_ID},
    )
    assert valid.status_code == 200
    assert valid.json()["validation"]["valid"] is True

    too_small = client.post(
        "/operator-portal/api/requirements/validate",
        json={"requirements": "too small", "app_id": REQUIRED_APP_ID},
    )
    assert too_small.status_code == 400
    assert too_small.json()["detail"]["errors"][0]["code"] == "requirements_too_small"

    unsafe_app_id = client.post(
        "/operator-portal/api/runs",
        json={"requirements": valid_requirements, "app_id": "../escape"},
    )
    assert unsafe_app_id.status_code == 400
    assert unsafe_app_id.json()["detail"]["errors"][0]["code"] == "invalid_app_id"

    bad_approval = client.post(
        "/operator-portal/api/portfolio/approvals",
        json={"action": "start", "scope": "runtime_contract_run", "actor": "operator", "approval_token": "wrong"},
    )
    assert bad_approval.status_code == 403

    bad_port = client.post(
        "/operator-portal/api/portfolio/runtime/start",
        json={
            "app_id": REQUIRED_APP_ID,
            "version_id": "v1",
            "run_id": "runtime_contract_run",
            "approval_nonce": "nonce_12345678",
            "port": 80,
        },
    )
    assert bad_port.status_code == 422

    approval = client.post(
        "/operator-portal/api/runs",
        json={"requirements": valid_requirements, "app_id": REQUIRED_APP_ID},
    ).json()
    run_id = approval["run_id"]
    assert client.post(f"/operator-portal/api/runs/{run_id}/execute").status_code == 409
    assert client.post(f"/operator-portal/api/runs/{run_id}/plan").status_code == 200
    assert client.post(
        f"/operator-portal/api/runs/{run_id}/approvals",
        json={"actor": "operator", "approval_token": APPROVAL_TOKEN},
    ).status_code == 200
