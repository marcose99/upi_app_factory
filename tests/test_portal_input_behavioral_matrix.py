from __future__ import annotations

from tests.test_portal_page_workflow_e2e import run_portal_vm_scenario


def test_requirements_actor_token_runtime_inputs_drive_exact_payloads() -> None:
    run_portal_vm_scenario(
        """
test.elements.get("requirements-input").value = "A".repeat(100);
test.elements.get("approval-actor").value = "reviewer";
test.elements.get("approval-token").value = "APPROVE_PORTAL_ENGINEERING";
test.setRoute("POST /operator-portal/api/runs/run_payload/approvals", {
  payload: {
    status: "approved",
    run: {
      run_id: "run_payload",
      state: "APPROVED",
      requirements_sha256: "sha",
      approval: true,
      updated_at_utc: "2026-07-20T00:00:01Z",
      events: [],
    },
  },
});
await test.button("validate-requirements").userClick();
await test.button("refresh-run").userClick();
await test.button("approve-engineering").userClick();
const validation = test.requests.find(
  (item) => item.path === "/operator-portal/api/requirements/validate",
);
const approval = test.requests.find(
  (item) => item.path === "/operator-portal/api/runs/run_payload/approvals",
);
test.assert.deepStrictEqual(validation, {
  path: "/operator-portal/api/requirements/validate",
  method: "POST",
  body: { requirements: "A".repeat(100) },
});
test.assert.deepStrictEqual(approval, {
  path: "/operator-portal/api/runs/run_payload/approvals",
  method: "POST",
  body: { actor: "reviewer", approval_token: "APPROVE_PORTAL_ENGINEERING" },
});
console.log(JSON.stringify({ payloads: true }));
""",
        pre_boot="""
preBoot.localStore.set("upi_app_factory_current_run_id", "run_payload");
preBoot.setRoute("GET /operator-portal/api/runs/run_payload", {
  payload: {
    run_id: "run_payload",
    state: "AWAITING_APPROVAL",
    requirements_sha256: "sha",
    approval: null,
    updated_at_utc: "2026-07-20T00:00:00Z",
    events: [],
  },
});
""",
    )


def test_runtime_selector_port_and_run_id_drive_runtime_payload() -> None:
    run_portal_vm_scenario(
        """
test.elements.get("runtime-run-id").value = "run_runtime_payload";
test.elements.get("runtime-port-input").value = "19091";
test.setRoute("POST /operator-portal/api/portfolio/runtime/start", {
  payload: {
    state: "READY",
    binding: { port: 19091 },
    health: { status: "ok" },
    mock_safe_local: true,
  },
});
await test.button("runtime-start").userClick();
const start = test.requests.find(
  (item) => item.path === "/operator-portal/api/portfolio/runtime/start",
);
test.assert.deepStrictEqual(start, {
  path: "/operator-portal/api/portfolio/runtime/start",
  method: "POST",
  body: {
    app_id: "demo_app",
    version_id: "v1",
    run_id: "run_runtime_payload",
    approval_nonce: "",
    port: 19091,
  },
});
test.assert.strictEqual(test.field("runtime-port").textContent, "19091");
console.log(JSON.stringify({ runtimePayload: true }));
"""
    )
