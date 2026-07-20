from __future__ import annotations

from tests.test_portal_page_workflow_e2e import run_portal_vm_scenario


def test_engineering_run_actions_share_one_conflict_domain() -> None:
    run_portal_vm_scenario(
        """
let release;
test.setRoute("POST /operator-portal/api/runs", () => new Promise((resolve) => {
  release = () => resolve({
    status: "run_created",
    run_id: "run_conflict",
    run: {
      run_id: "run_conflict",
      state: "REQUIREMENTS_ACCEPTED",
      requirements_sha256: "sha",
      approval: null,
      updated_at_utc: "2026-07-20T00:00:00Z",
      events: [],
    },
  });
}));
const pending = test.button("submit-run").userClick();
await Promise.resolve();
for (const action of ["generate-plan", "approve-engineering", "start-engineering", "cancel-run"]) {
  test.assert.strictEqual(test.button(action).disabled, true, action);
  test.assert.strictEqual(test.button(action).getAttribute("aria-disabled"), "true", action);
}
test.assert.strictEqual(test.button("runtime-start").disabled, false);
release();
await pending;
console.log(JSON.stringify({ engineeringDomain: true }));
"""
    )


def test_runtime_version_action_conflicts_only_with_runtime_version_domain() -> None:
    run_portal_vm_scenario(
        """
let release;
test.setRoute("POST /operator-portal/api/portfolio/runtime/start", () => new Promise((resolve) => {
  release = () => resolve({
    state: "READY",
    binding: { port: 18042 },
    health: { status: "ok" },
    mock_safe_local: true,
  });
}));
const pending = test.button("runtime-start").userClick();
await Promise.resolve();
for (const action of ["runtime-restart", "runtime-stop", "runtime-stop-all"]) {
  test.assert.strictEqual(test.button(action).disabled, true, action);
}
test.assert.strictEqual(test.button("submit-run").disabled, false);
test.assert.strictEqual(test.button("validation-run").disabled, false);
release();
await pending;
console.log(JSON.stringify({ runtimeVersionDomain: true }));
"""
    )


def test_validation_and_download_have_independent_conflict_domains() -> None:
    run_portal_vm_scenario(
        """
let release;
test.setRoute("POST /portal/validation-runner/run", () => new Promise((resolve) => {
  release = () => resolve({ status: "passed", report: { command_results: [] } });
}));
const pending = test.button("validation-run").userClick();
await Promise.resolve();
test.assert.strictEqual(test.button("validation-run").disabled, true);
test.assert.strictEqual(test.button("export-download").disabled, false);
test.assert.strictEqual(test.button("submit-run").disabled, false);
release();
await pending;
console.log(JSON.stringify({ validationDomain: true }));
"""
    )
