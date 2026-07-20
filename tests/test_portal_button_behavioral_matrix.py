from __future__ import annotations

from tests.test_portal_page_workflow_e2e import run_portal_vm_scenario


def test_duplicate_activation_is_suppressed_for_same_action() -> None:
    run_portal_vm_scenario(
        """
let release;
test.setRoute("POST /operator-portal/api/runs", () => new Promise((resolve) => {
  release = () => resolve({
    status: "run_created",
    run_id: "run_20260720T000000Z_abcdefghijklmnopqrstu2",
    run: {
      run_id: "run_20260720T000000Z_abcdefghijklmnopqrstu2",
      state: "REQUIREMENTS_ACCEPTED",
      requirements_sha256: "sha",
      approval: null,
      updated_at_utc: "2026-07-20T00:00:00Z",
      final_decision: null,
      events: [],
    },
  });
}));
const first = test.button("submit-run").userClick();
const second = test.button("submit-run").userClick();
await Promise.resolve();
test.assert.strictEqual(second instanceof Promise, true);
release();
await Promise.all([first, second]);
const submissions = test.requests.filter((item) => item.path === "/operator-portal/api/runs");
test.assert.strictEqual(submissions.length, 1);
console.log(JSON.stringify({ submissions: submissions.length }));
"""
    )


def test_runtime_global_action_conflicts_with_version_runtime_actions() -> None:
    run_portal_vm_scenario(
        """
let release;
const stopAllRoute = "POST /operator-portal/api/portfolio/runtime/stop-all?approval_nonce=";
test.setRoute(stopAllRoute, () => new Promise((resolve) => {
  release = () => resolve({ status: "stopped", stopped: [] });
}));
const stopAll = test.button("runtime-stop-all").userClick();
await Promise.resolve();
test.assert.strictEqual(test.button("runtime-start").disabled, true);
test.assert.strictEqual(test.button("runtime-restart").disabled, true);
test.assert.strictEqual(test.button("runtime-stop").disabled, true);
test.assert.strictEqual(test.button("runtime-evidence").disabled, true);
release();
await stopAll;
test.assert.strictEqual(test.button("runtime-start").disabled, false);
console.log(JSON.stringify({ runtimeGlobalConflict: true }));
"""
    )
