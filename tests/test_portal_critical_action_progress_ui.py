from __future__ import annotations

from tests.test_portal_page_workflow_e2e import run_portal_vm_scenario


def test_critical_action_lock_spinner_aria_busy_and_server_progress_lifecycle() -> None:
    run_portal_vm_scenario(
        """
let releaseSubmit;
test.setRoute("POST /operator-portal/api/runs", () => new Promise((resolve) => {
  releaseSubmit = () => resolve({
    status: "run_created",
    run_id: "run_20260720T000000Z_abcdefghijklmnopqrstu1",
    run: {
      run_id: "run_20260720T000000Z_abcdefghijklmnopqrstu1",
      state: "EXECUTING",
      progress_percent: 47,
      requirements_sha256: "sha",
      approval: null,
      updated_at_utc: "2026-07-20T00:00:00Z",
      final_decision: null,
      events: [],
      artifacts: {},
    },
  });
}));
const button = test.button("submit-run");
const first = button.userClick();
await Promise.resolve();
test.assert.strictEqual(button.getAttribute("aria-busy"), "true");
test.assert.ok(button.innerHTML.includes("spinner"));
test.assert.strictEqual(test.button("generate-plan").disabled, true);
test.assert.strictEqual(test.button("cancel-run").disabled, true);
test.assert.strictEqual(test.button("validation-run").disabled, false);
releaseSubmit();
await first;
test.assert.strictEqual(button.getAttribute("aria-busy"), null);
test.assert.strictEqual(test.elements.get("run-progress-panel").hidden, false);
test.assert.strictEqual(test.elements.get("run-progress").value, 47);
test.assert.match(test.elements.get("run-progress-status").textContent, /EXECUTING/);
console.log(JSON.stringify({ requests: test.requests.length }));
"""
    )


def test_terminal_progress_restores_control_lock_state() -> None:
    run_portal_vm_scenario(
        """
test.assert.strictEqual(test.field("browser-run-id").textContent, "run_existing");
test.assert.strictEqual(test.elements.get("run-progress").value, 100);
test.assert.strictEqual(test.button("submit-run").disabled, false);
test.assert.strictEqual(test.button("cancel-run").disabled, true);
test.assert.strictEqual(test.link("download-application").getAttribute("aria-disabled"), "false");
console.log(JSON.stringify({ restored: true }));
""",
        pre_boot="""
preBoot.localStore.set("upi_app_factory_current_run_id", "run_existing");
preBoot.setRoute("GET /operator-portal/api/runs/run_existing", {
  payload: {
    run_id: "run_existing",
    state: "SUCCEEDED",
    progress_percent: 100,
    requirements_sha256: "sha",
    approval: true,
    updated_at_utc: "2026-07-20T00:00:00Z",
    final_decision: "completed",
    events: [],
    artifacts: { generated_application_available: true },
  },
});
""",
    )
