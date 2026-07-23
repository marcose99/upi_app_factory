from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path


def run_portal_vm_scenario(scenario: str, *, pre_boot: str = "") -> None:
    root = Path(__file__).resolve().parents[1]
    app_js = root / "factory" / "operator_portal" / "web_ui" / "static" / "app.js"
    harness = f"""
const assert = require("assert");
const vm = require("vm");
const appSource = {json.dumps(app_js.read_text(encoding="utf-8"))};
const preBootSource = {json.dumps(pre_boot)};
const scenarioSource = {json.dumps(scenario)};

class LocalStore {{
  constructor() {{
    this.values = new Map();
  }}
  getItem(key) {{
    return this.values.has(key) ? this.values.get(key) : null;
  }}
  get(key) {{
    return this.getItem(key);
  }}
  setItem(key, value) {{
    this.values.set(key, String(value));
  }}
  set(key, value) {{
    this.setItem(key, value);
  }}
  removeItem(key) {{
    this.values.delete(key);
  }}
}}

class Element {{
  constructor(tagName, id = "") {{
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.attributes = new Map();
    this.dataset = {{}};
    this.children = [];
    this.eventListeners = new Map();
    this.classList = {{
      values: new Set(),
      toggle: (name, force) => {{
        if (force) {{
          this.classList.values.add(name);
        }} else {{
          this.classList.values.delete(name);
        }}
      }},
    }};
    this.textContent = "";
    this.innerHTML = "";
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.href = "#";
    this.selectedIndex = 0;
  }}
  get options() {{
    return this.children.filter((child) => child.tagName === "OPTION");
  }}
  appendChild(child) {{
    this.children.push(child);
    if (this.tagName === "SELECT" && !this.value && child.value !== undefined) {{
      this.value = child.value;
      this.selectedIndex = Math.max(0, this.children.length - 1);
    }}
    return child;
  }}
  setAttribute(name, value) {{
    this.attributes.set(name, String(value));
    if (name === "id") {{
      this.id = String(value);
    }}
    if (name === "href") {{
      this.href = String(value);
    }}
    if (name.startsWith("data-")) {{
      const key = name
        .slice(5)
        .replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      this.dataset[key] = String(value);
    }}
  }}
  getAttribute(name) {{
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }}
  removeAttribute(name) {{
    this.attributes.delete(name);
  }}
  addEventListener(name, callback) {{
    if (!this.eventListeners.has(name)) {{
      this.eventListeners.set(name, []);
    }}
    this.eventListeners.get(name).push(callback);
  }}
  async userClick() {{
    const listeners = this.eventListeners.get("click") || [];
    const results = listeners.map((listener) => listener({{ target: this }}));
    return Promise.all(results);
  }}
}}

class Document {{
  constructor() {{
    this.byId = new Map();
    this.elements = [];
  }}
  register(element) {{
    this.elements.push(element);
    if (element.id) {{
      this.byId.set(element.id, element);
    }}
    return element;
  }}
  createElement(tagName) {{
    return new Element(tagName);
  }}
  getElementById(id) {{
    return this.byId.get(id) || null;
  }}
  querySelector(selector) {{
    return this.querySelectorAll(selector)[0] || null;
  }}
  querySelectorAll(selector) {{
    const dataMatch = selector.match(/^\\[data-([^=\\]]+)(?:="([^"]+)")?\\]$/);
    if (dataMatch) {{
      const key = dataMatch[1].replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      const expected = dataMatch[2];
      return this.elements.filter((element) => {{
        if (!(key in element.dataset)) {{
          return false;
        }}
        return expected === undefined || element.dataset[key] === expected;
      }});
    }}
    return [];
  }}
}}

function registerFixture(document) {{
  const ids = [
    "requirements-input",
    "app-id-input",
    "approval-actor",
    "approval-token",
    "run-progress-panel",
    "run-progress",
    "run-progress-status",
    "run-events",
    "validation-summary",
    "error-summary",
    "report-output",
    "runtime-output",
    "runtime-version-selector",
    "runtime-run-id",
    "runtime-port-input",
    "guide-list",
  ];
  for (const id of ids) {{
    const tag = id === "runtime-version-selector" ? "select" : id === "guide-list" ? "ul" : "div";
    document.register(new Element(tag, id));
  }}
  document.getElementById("requirements-input").value = "# UPI dispute resolution requirements";
  document.getElementById("app-id-input").value = "upi_failed_debit_no_credit";
  document.getElementById("approval-actor").value = "operator";
  document.getElementById("approval-token").value = "";
  document.getElementById("runtime-run-id").value = "portfolio_runtime_001";
  document.getElementById("runtime-port-input").value = "18042";
  for (const field of [
    "health-status", "health-phase", "health-service", "evidence-posture",
    "evidence-current", "evidence-claim", "download-status", "download-ready",
    "download-path", "dry-run-status", "run-status", "latest-status",
    "browser-run-id", "browser-run-state", "browser-run-sha",
    "browser-approval-state", "browser-updated-at", "browser-final-decision",
    "runtime-selected-app", "runtime-selected-version", "runtime-state",
    "runtime-health", "runtime-port", "runtime-mock-safe", "guides-status",
    "guides-count", "taxonomy-count", "debug-plan-schema", "debug-plan-routes",
    "debug-plan-sha", "factory-docs-status", "factory-docs-size",
    "factory-docs-route",
  ]) {{
    const element = document.register(new Element("dd"));
    element.setAttribute("data-field", field);
  }}
  const actions = [
    "refresh-health", "refresh-evidence", "refresh-download", "export-download",
    "validation-dry-run", "validation-run", "latest-report", "refresh-guides",
    "view-factory-debug-plan", "view-factory-documentation",
    "refresh-run", "validate-requirements", "submit-run", "generate-plan",
    "approve-engineering", "start-engineering", "cancel-run",
    "view-validation-report", "view-evidence", "runtime-approve-start",
    "runtime-start", "runtime-openapi", "runtime-scenarios",
    "runtime-approve-restart", "runtime-restart", "runtime-approve-stop",
    "runtime-stop", "runtime-approve-stop-all", "runtime-stop-all",
    "runtime-evidence",
  ];
  for (const action of actions) {{
    const element = document.register(new Element("button", `${{action}}-button`));
    element.textContent = action;
    element.setAttribute("data-action", action);
  }}
  for (const link of ["download-application", "download-evidence", "download-factory-debug-plan", "download-factory-documentation"]) {{
    const element = document.register(new Element("a", `${{link}}-button`));
    element.setAttribute("data-link", link);
    element.setAttribute("aria-disabled", "true");
  }}
}}

const routes = new Map();
const requests = [];
const localStore = new LocalStore();
const document = new Document();
registerFixture(document);

function setRoute(key, value) {{
  const parts = key.split(" ");
  if (parts.length > 1 && /^(GET|POST|PUT|PATCH|DELETE)$/.test(parts[0])) {{
    routes.set(`${{parts[0]}} ${{parts.slice(1).join(" ")}}`, value);
  }} else {{
    routes.set(`GET ${{key}}`, value);
    routes.set(key, value);
  }}
}}

function defaultRoutes() {{
  setRoute("GET /health", {{ status: "ok", phase: "local", service: "operator_portal" }});
  setRoute("GET /portal/evidence-dashboard", {{
    payload: {{ phase_coverage: {{ posture: "certification_ready_not_certified", current: "available" }} }},
  }});
  setRoute("GET /portal/download-center/status", {{
    status: "ready",
    download_center: {{ status: "ready" }},
    phase31_export_bundle_metadata: {{ bundle_ready: false }},
  }});
  setRoute("GET /portal/operator-guides", {{
    status: "available",
    payload: {{ status: "available", guides: [], status_taxonomy: {{}} }},
  }});
  setRoute("GET /operator-portal/api/portfolio/catalogue", {{
    versions: [{{ app_id: "demo_app", version_id: "v1" }}],
  }});
}}

function responsePayload(value) {{
  if (typeof value === "function") {{
    value = value();
  }}
  return Promise.resolve(value).then((resolved) => {{
    if (resolved && Object.prototype.hasOwnProperty.call(resolved, "payload")) {{
      return resolved.payload;
    }}
    return resolved;
  }});
}}

async function fetch(path, options = {{}}) {{
  const method = options.method || "GET";
  let body = undefined;
  if (options.body) {{
    body = JSON.parse(options.body);
  }}
  requests.push({{ path, method, body }});
  const key = `${{method}} ${{path}}`;
  const route = routes.has(key) ? routes.get(key) : routes.get(path);
  if (route === undefined) {{
    throw new Error(`No mocked route for ${{key}}`);
  }}
  const payload = await responsePayload(route);
  return {{
    ok: true,
    status: 200,
    json: async () => payload,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  }};
}}

const windowListeners = new Map();
const windowObject = {{
  localStorage: localStore,
  setInterval: () => 1,
  clearInterval: () => undefined,
  addEventListener: (name, callback) => windowListeners.set(name, callback),
}};
const harnessAssert = {{
  strictEqual: assert.strictEqual,
  ok: assert.ok,
  match: assert.match,
  deepStrictEqual: (actual, expected, message) =>
    assert.deepStrictEqual(
      JSON.parse(JSON.stringify(actual)),
      JSON.parse(JSON.stringify(expected)),
      message,
    ),
}};

const context = {{
  assert,
  console,
  document,
  fetch,
  window: windowObject,
  Promise,
  Error,
  JSON,
  Number,
  String,
  Boolean,
  Array,
  Map,
  Set,
}};
context.globalThis = context;
defaultRoutes();
const preBoot = {{ localStore, setRoute }};
vm.createContext(context);
vm.runInContext(preBootSource, vm.createContext({{ preBoot, Promise, console }}));
vm.runInContext(appSource, context);
const boot = windowListeners.get("DOMContentLoaded");
if (!boot) {{
  throw new Error("Portal app did not register DOMContentLoaded boot handler.");
}}
async function triggerBoot() {{
  boot();
  for (let index = 0; index < 25; index += 1) {{
    await Promise.resolve();
  }}
}}
triggerBoot().then(async () => {{
  const test = {{
    assert: harnessAssert,
    requests,
    localStore,
    elements: document.byId,
    setRoute,
    button: (action) => document.querySelector(`[data-action="${{action}}"]`),
    link: (name) => document.querySelector(`[data-link="${{name}}"]`),
    field: (name) => document.querySelector(`[data-field="${{name}}"]`),
  }};
  context.test = test;
  await vm.runInContext(`(async () => {{\\n${{scenarioSource}}\\n}})()`, context);
}}).catch((error) => {{
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
}});
"""
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(harness)],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
      raise AssertionError(result.stderr or result.stdout)


def test_browser_page_workflow_creates_plans_approves_executes_and_polls() -> None:
    run_portal_vm_scenario(
        """
test.setRoute("POST /operator-portal/api/runs", {
  payload: {
    status: "run_created",
    run_id: "run_workflow",
    run: {
      run_id: "run_workflow",
      state: "REQUIREMENTS_ACCEPTED",
      requirements_sha256: "sha",
      approval: null,
      updated_at_utc: "2026-07-20T00:00:00Z",
      events: [{ event: "run_created" }],
    },
  },
});
test.setRoute("POST /operator-portal/api/runs/run_workflow/plan", {
  payload: {
    status: "plan_ready",
    run: {
      run_id: "run_workflow",
      state: "AWAITING_APPROVAL",
      requirements_sha256: "sha",
      approval: null,
      updated_at_utc: "2026-07-20T00:00:01Z",
      events: [{ event: "plan_ready" }],
    },
  },
});
test.setRoute("POST /operator-portal/api/runs/run_workflow/approvals", {
  payload: {
    status: "approved",
    run: {
      run_id: "run_workflow",
      state: "APPROVED",
      requirements_sha256: "sha",
      approval: true,
      updated_at_utc: "2026-07-20T00:00:02Z",
      events: [{ event: "approved" }],
    },
  },
});
let pollCount = 0;
test.setRoute("POST /operator-portal/api/runs/run_workflow/execute", {
  payload: {
    status: "accepted",
    run: {
      run_id: "run_workflow",
      state: "EXECUTION_QUEUED",
      progress_percent: 25,
      requirements_sha256: "sha",
      approval: true,
      updated_at_utc: "2026-07-20T00:00:03Z",
      events: [{ event: "execution_queued" }],
    },
  },
});
test.setRoute("GET /operator-portal/api/runs/run_workflow", () => {
  pollCount += 1;
  return {
    run_id: "run_workflow",
    state: pollCount === 1 ? "VALIDATING" : "SUCCEEDED",
    progress_percent: pollCount === 1 ? 88 : 100,
    requirements_sha256: "sha",
    approval: true,
    updated_at_utc: "2026-07-20T00:00:04Z",
    final_decision: pollCount === 1 ? null : "completed",
    events: [{ event: "poll", count: pollCount }],
    artifacts: { generated_application_available: pollCount > 1 },
  };
});
await test.button("submit-run").userClick();
await test.button("generate-plan").userClick();
await test.button("approve-engineering").userClick();
await test.button("start-engineering").userClick();
test.assert.strictEqual(test.field("browser-run-state").textContent, "VALIDATING");
test.assert.strictEqual(test.elements.get("run-progress").value, 88);
await test.button("refresh-run").userClick();
test.assert.strictEqual(test.field("browser-run-state").textContent, "SUCCEEDED");
test.assert.strictEqual(test.link("download-application").getAttribute("aria-disabled"), "false");
console.log(JSON.stringify({ pollCount }));
"""
    )


def test_reload_restores_current_run_from_local_storage() -> None:
    run_portal_vm_scenario(
        """
test.assert.strictEqual(test.field("browser-run-id").textContent, "run_reloaded");
test.assert.strictEqual(test.field("browser-run-state").textContent, "EXECUTING");
test.assert.strictEqual(test.elements.get("run-progress").value, 64);
console.log(JSON.stringify({ restored: test.localStore.get("upi_app_factory_current_run_id") }));
""",
        pre_boot="""
preBoot.localStore.set("upi_app_factory_current_run_id", "run_reloaded");
preBoot.setRoute("GET /operator-portal/api/runs/run_reloaded", {
  payload: {
    run_id: "run_reloaded",
    state: "EXECUTING",
    progress_percent: 64,
    requirements_sha256: "sha",
    approval: true,
    updated_at_utc: "2026-07-20T00:00:00Z",
    events: [{ event: "execution_started" }],
  },
});
""",
    )
