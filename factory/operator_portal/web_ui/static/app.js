(function () {
  "use strict";

  const fields = new Map();
  let currentRunId = "";
  let pollTimer = 0;
  let runtimeStartNonce = "";
  let runtimeRestartNonce = "";
  let runtimeStopNonce = "";
  let runtimeStopAllNonce = "";
  let selectedRuntimeVersion = null;
  const inFlightActions = new Map();
  const actionLockDomains = {
    "submit-run": ["engineering-run"],
    "generate-plan": ["engineering-run"],
    "approve-engineering": ["engineering-run"],
    "start-engineering": ["engineering-run"],
    "cancel-run": ["engineering-run"],
    "runtime-approve-start": ["runtime"],
    "runtime-start": ["runtime-version"],
    "runtime-approve-restart": ["runtime"],
    "runtime-restart": ["runtime-version"],
    "runtime-approve-stop": ["runtime"],
    "runtime-stop": ["runtime-version"],
    "runtime-approve-stop-all": ["runtime-global"],
    "runtime-stop-all": ["runtime-global", "runtime-version"],
    "validation-run": ["validation"],
    "export-download": ["download-export"],
  };

  function field(name) {
    if (!fields.has(name)) {
      fields.set(name, document.querySelector(`[data-field="${name}"]`));
    }
    return fields.get(name);
  }

  function setField(name, value) {
    const node = field(name);
    if (node) {
      node.textContent = value === undefined || value === null ? "Unavailable" : String(value);
    }
  }

  function showReport(payload) {
    const output = document.getElementById("report-output");
    if (output) {
      output.textContent = JSON.stringify(payload, null, 2);
    }
  }

  function showError(message) {
    const output = document.getElementById("error-summary");
    if (output) {
      output.textContent = message || "No errors.";
    }
  }

  function showRunEvents(events) {
    const output = document.getElementById("run-events");
    if (output) {
      output.textContent = JSON.stringify(events || [], null, 2);
    }
  }

  function showValidation(payload) {
    const output = document.getElementById("validation-summary");
    if (output) {
      output.textContent = JSON.stringify(payload, null, 2);
    }
  }

  function showRuntime(payload) {
    const output = document.getElementById("runtime-output");
    if (output) {
      output.textContent = JSON.stringify(payload, null, 2);
    }
    if (payload && payload.state) {
      setField("runtime-state", payload.state);
      setField("runtime-port", payload.binding ? payload.binding.port : "18042");
      setField("runtime-health", payload.health ? payload.health.status : "Unavailable");
      setField("runtime-mock-safe", payload.mock_safe_local);
    }
  }

  function runtimeSelector() {
    return document.getElementById("runtime-version-selector");
  }

  function runtimePort() {
    const node = document.getElementById("runtime-port-input");
    const value = node ? Number.parseInt(node.value, 10) : 18042;
    return Number.isFinite(value) ? value : 18042;
  }

  function portfolioRuntimeRunId() {
    const node = document.getElementById("runtime-run-id");
    return node && node.value.trim() ? node.value.trim() : "portfolio_runtime_001";
  }

  function selectedRuntimeIdentity() {
    if (!selectedRuntimeVersion) {
      throw new Error("Select a registered application/version before runtime operations.");
    }
    return selectedRuntimeVersion;
  }

  function renderRuntimeSelector(versions) {
    const selector = runtimeSelector();
    if (!selector) {
      return;
    }
    selector.textContent = "";
    if (!versions.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No registered versions";
      selector.appendChild(option);
      selectedRuntimeVersion = null;
      setField("runtime-selected-app", "No registered version");
      setField("runtime-selected-version", "No registered version");
      return;
    }
    versions.forEach((version) => {
      const option = document.createElement("option");
      option.value = `${version.app_id}:${version.version_id}`;
      option.textContent = `${version.app_id} / ${version.version_id}`;
      option.dataset.appId = version.app_id;
      option.dataset.versionId = version.version_id;
      selector.appendChild(option);
    });
    const saved = window.localStorage.getItem("upi_app_factory_runtime_selection");
    if (saved && versions.some((version) => `${version.app_id}:${version.version_id}` === saved)) {
      selector.value = saved;
    }
    const selected = versions.find((version) => `${version.app_id}:${version.version_id}` === selector.value) || versions[0];
    selectedRuntimeVersion = selected;
    selector.value = `${selected.app_id}:${selected.version_id}`;
    window.localStorage.setItem("upi_app_factory_runtime_selection", selector.value);
    setField("runtime-selected-app", selected.app_id);
    setField("runtime-selected-version", selected.version_id);
  }

  async function refreshPortfolioCatalogue() {
    const payload = await request("/operator-portal/api/portfolio/catalogue");
    const versions = Array.isArray(payload.versions) ? payload.versions : [];
    renderRuntimeSelector(versions);
    return payload;
  }

  function formatErrorDetail(detail, status) {
    if (detail && typeof detail === "object") {
      return {
        status: detail.status || "error",
        operator_message:
          detail.operator_message || `Request failed with HTTP status ${status}.`,
        next_steps: Array.isArray(detail.next_steps) ? detail.next_steps : [],
        error: detail.error || undefined,
        safety_boundaries: detail.safety_boundaries || undefined,
      };
    }
    return {
      status: "error",
      operator_message: detail || `Request failed with HTTP status ${status}.`,
      next_steps: ["Check that the local portal server is running and retry the action."],
    };
  }

  async function request(path, options) {
    let response;
    try {
      response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    } catch (error) {
      throw new Error(
        `Local portal request could not be sent. Check the local server process. ${String(error)}`,
      );
    }
    const payload = await response.json();
    if (!response.ok) {
      const detail = formatErrorDetail(payload.detail, response.status);
      throw new Error(JSON.stringify(detail, null, 2));
    }
    showError("No errors.");
    return payload;
  }

  async function requestPlain(path, options) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      throw new Error(`Request failed with HTTP status ${response.status}.`);
    }
    return response.text();
  }

  function requirementsText() {
    const node = document.getElementById("requirements-input");
    return node ? node.value : "";
  }

  function updateDownloadLinks(run) {
    const artifacts = run && run.artifacts ? run.artifacts : {};
    const appLink = document.querySelector('[data-link="download-application"]');
    const evidenceLink = document.querySelector('[data-link="download-evidence"]');
    if (appLink) {
      const enabled = Boolean(
        currentRunId && run && run.state === "SUCCEEDED" && artifacts.generated_application_available,
      );
      appLink.href = enabled
        ? `/operator-portal/api/runs/${currentRunId}/downloads/application`
        : "#";
      appLink.classList.toggle("disabled", !enabled);
      appLink.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
    if (evidenceLink) {
      const enabled = Boolean(
        currentRunId && run && ["SUCCEEDED", "FAILED", "CANCELLED"].includes(run.state),
      );
      evidenceLink.href = enabled
        ? `/operator-portal/api/runs/${currentRunId}/downloads/evidence`
        : "#";
      evidenceLink.classList.toggle("disabled", !enabled);
      evidenceLink.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
  }

  function setEnabled(id, enabled) {
    const node = document.getElementById(id);
    if (node) {
      node.disabled = !enabled;
      node.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
  }

  function progressValueForState(state) {
    const values = {
      EXECUTION_QUEUED: 35,
      EXECUTING: 60,
      VALIDATING: 85,
      SUCCEEDED: 100,
      FAILED: 100,
      CANCELLED: 100,
    };
    return values[state] || 0;
  }

  function progressValueForRun(run) {
    if (run && typeof run.progress_percent === "number" && Number.isFinite(run.progress_percent)) {
      return Math.max(0, Math.min(100, run.progress_percent));
    }
    return progressValueForState(run ? run.state : "");
  }

  function updateProgress(run) {
    const panel = document.getElementById("run-progress-panel");
    const progress = document.getElementById("run-progress");
    const status = document.getElementById("run-progress-status");
    if (!panel || !progress || !status) {
      return;
    }
    const state = run ? run.state : "";
    const active = ["EXECUTION_QUEUED", "EXECUTING", "VALIDATING"].includes(state);
    const terminal = ["SUCCEEDED", "FAILED", "CANCELLED"].includes(state);
    panel.hidden = !(active || terminal);
    progress.value = progressValueForRun(run);
    status.textContent = active
      ? `Engineering run ${currentRunId} is ${state}.`
      : terminal
        ? `Engineering run ${currentRunId} reached ${state}.`
        : "No critical operation active.";
  }

  function updateControls(run) {
    const state = run ? run.state : "";
    const hasRun = Boolean(currentRunId);
    const busy = ["EXECUTION_QUEUED", "EXECUTING", "VALIDATING"].includes(state);
    setEnabled(
      "generate-plan-button",
      hasRun && ["REQUIREMENTS_ACCEPTED", "PLAN_READY", "AWAITING_APPROVAL"].includes(state),
    );
    setEnabled("approve-engineering-button", hasRun && state === "AWAITING_APPROVAL");
    setEnabled("start-engineering-button", hasRun && state === "APPROVED");
    setEnabled("cancel-run-button", hasRun && !["SUCCEEDED", "FAILED", "CANCELLED"].includes(state));
    setEnabled("refresh-run-button", hasRun);
    setEnabled("view-validation-button", hasRun);
    setEnabled("view-evidence-button", hasRun);
    setEnabled("validate-requirements-button", !busy);
    setEnabled("submit-run-button", !busy);
  }

  function renderRun(run) {
    if (!run) {
      return;
    }
    currentRunId = run.run_id || currentRunId;
    if (currentRunId) {
      window.localStorage.setItem("upi_app_factory_current_run_id", currentRunId);
    }
    setField("browser-run-id", currentRunId || "Not created");
    setField("browser-run-state", run.state);
    setField("browser-run-sha", run.requirements_sha256);
    setField("browser-approval-state", run.approval ? "approved" : "required");
    setField("browser-updated-at", run.updated_at_utc);
    setField("browser-final-decision", run.final_decision || "Waiting");
    showRunEvents(run.events || []);
    updateDownloadLinks(run);
    updateControls(run);
    updateProgress(run);
  }

  async function refreshCurrentRun() {
    if (!currentRunId) {
      return;
    }
    const run = await request(`/operator-portal/api/runs/${currentRunId}`);
    renderRun(run);
    if (["EXECUTION_QUEUED", "EXECUTING", "VALIDATING"].includes(run.state)) {
      if (!pollTimer) {
        pollTimer = window.setInterval(() => {
          refreshCurrentRun().catch((error) =>
            showReport({ error: error instanceof Error ? error.message : String(error) }),
          );
        }, 1000);
      }
    } else if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = 0;
    }
  }

  async function refreshHealth() {
    const payload = await request("/health");
    setField("health-status", payload.status);
    setField("health-phase", payload.phase);
    setField("health-service", payload.service);
  }

  async function refreshEvidence() {
    const payload = await request("/portal/evidence-dashboard");
    const summary = payload.payload || {};
    const coverage = summary.phase_coverage || {};
    setField("evidence-posture", coverage.posture);
    setField("evidence-current", coverage.current);
    setField("evidence-claim", summary.dashboard_success_claim || "available");
  }

  async function refreshDownload() {
    const payload = await request("/portal/download-center/status");
    const center = payload.download_center || {};
    const bundle = payload.phase31_export_bundle_metadata || {};
    setField("download-status", center.status || payload.status);
    setField("download-ready", bundle.bundle_ready);
    setField("download-path", bundle.zip_path || "No bundle path reported");
  }

  async function exportDownload() {
    setField("download-status", "Export running");
    const payload = await request("/portal/download-center/export", { method: "POST" });
    const metadata = payload.export ? payload.export.bundle_metadata || {} : {};
    setField("download-status", payload.status);
    setField("download-ready", payload.status === "export_ready");
    setField("download-path", payload.export ? payload.export.bundle_path : metadata.bundle_id);
    showReport(payload);
  }

  async function validationDryRun() {
    const payload = await request("/portal/validation-runner/dry-run");
    const report = payload.report || {};
    const count = Array.isArray(report.command_results) ? report.command_results.length : 0;
    setField("dry-run-status", `${payload.status}: ${count} approved commands`);
    showReport(payload);
  }

  async function validationRun() {
    setField("run-status", "Running safe self-check");
    const payload = await request("/portal/validation-runner/run", {
      method: "POST",
      body: JSON.stringify({
        command_ids: ["phase34_runner_self_check"],
        collect_all: true,
        write_report: true,
      }),
    });
    setField("run-status", payload.status);
    showReport(payload);
  }

  async function latestReport() {
    const payload = await request("/portal/validation-runner/latest-report");
    setField("latest-status", payload.status);
    showReport(payload);
  }

  async function validateRequirements() {
    const payload = await request("/operator-portal/api/requirements/validate", {
      method: "POST",
      body: JSON.stringify({ requirements: requirementsText() }),
    });
    setField("browser-run-sha", payload.validation.sha256);
    showReport(payload);
  }

  async function submitRun() {
    const payload = await request("/operator-portal/api/runs", {
      method: "POST",
      body: JSON.stringify({ requirements: requirementsText() }),
    });
    currentRunId = payload.run_id;
    renderRun(payload.run);
    showReport(payload);
  }

  async function generatePlan() {
    if (!currentRunId) {
      throw new Error("Create a run before generating a plan.");
    }
    const payload = await request(`/operator-portal/api/runs/${currentRunId}/plan`, {
      method: "POST",
    });
    renderRun(payload.run);
    showReport(payload);
  }

  async function approveEngineering() {
    if (!currentRunId) {
      throw new Error("Create a run before recording approval.");
    }
    const actor = document.getElementById("approval-actor");
    const token = document.getElementById("approval-token");
    const payload = await request(`/operator-portal/api/runs/${currentRunId}/approvals`, {
      method: "POST",
      body: JSON.stringify({
        actor: actor ? actor.value : "operator",
        approval_token: token ? token.value : "",
      }),
    });
    renderRun(payload.run);
    showReport(payload);
  }

  async function startEngineering() {
    if (!currentRunId) {
      throw new Error("Create a run before starting application engineering.");
    }
    const payload = await request(`/operator-portal/api/runs/${currentRunId}/execute`, {
      method: "POST",
    });
    renderRun(payload.run);
    showReport(payload);
    await refreshCurrentRun();
  }

  async function cancelRun() {
    if (!currentRunId) {
      throw new Error("Create a run before cancelling.");
    }
    const payload = await request(`/operator-portal/api/runs/${currentRunId}/cancel`, {
      method: "POST",
    });
    renderRun(payload.run);
    showReport(payload);
  }

  async function viewValidationReport() {
    if (!currentRunId) {
      await latestReport();
      return;
    }
    const payload = await request(`/operator-portal/api/runs/${currentRunId}/validation`);
    showValidation(payload);
    const events = await request(`/operator-portal/api/runs/${currentRunId}/events`);
    showRunEvents(events.events || []);
    showReport(payload);
  }

  async function viewEvidence() {
    if (!currentRunId) {
      throw new Error("Create a run before viewing run evidence.");
    }
    const payload = await request(`/operator-portal/api/runs/${currentRunId}/evidence`);
    showReport(payload);
  }

  async function runtimeApprove(action) {
    if (action !== "stop_all") {
      selectedRuntimeIdentity();
    }
    const token = document.getElementById("approval-token");
    const actor = document.getElementById("approval-actor");
    const runId = portfolioRuntimeRunId();
    const payload = await request("/operator-portal/api/portfolio/approvals", {
      method: "POST",
      body: JSON.stringify({
        action,
        scope: action === "stop_all" ? "portfolio" : runId,
        actor: actor ? actor.value : "operator",
        approval_token: token ? token.value : "",
      }),
    });
    if (action === "start") {
      runtimeStartNonce = payload.nonce;
    }
    if (action === "restart") {
      runtimeRestartNonce = payload.nonce;
    }
    if (action === "stop") {
      runtimeStopNonce = payload.nonce;
    }
    if (action === "stop_all") {
      runtimeStopAllNonce = payload.nonce;
    }
    showRuntime(payload);
  }

  async function runtimeStart() {
    const identity = selectedRuntimeIdentity();
    const payload = await request("/operator-portal/api/portfolio/runtime/start", {
      method: "POST",
      body: JSON.stringify({
        app_id: identity.app_id,
        version_id: identity.version_id,
        run_id: portfolioRuntimeRunId(),
        approval_nonce: runtimeStartNonce,
        port: runtimePort(),
      }),
    });
    showRuntime(payload);
  }

  async function runtimeStop() {
    const identity = selectedRuntimeIdentity();
    const payload = await request("/operator-portal/api/portfolio/runtime/stop", {
      method: "POST",
      body: JSON.stringify({
        app_id: identity.app_id,
        version_id: identity.version_id,
        run_id: portfolioRuntimeRunId(),
        approval_nonce: runtimeStopNonce,
        port: runtimePort(),
      }),
    });
    showRuntime(payload);
  }

  async function runtimeRestart() {
    const identity = selectedRuntimeIdentity();
    const payload = await request("/operator-portal/api/portfolio/runtime/restart", {
      method: "POST",
      body: JSON.stringify({
        app_id: identity.app_id,
        version_id: identity.version_id,
        run_id: portfolioRuntimeRunId(),
        approval_nonce: runtimeRestartNonce,
        port: runtimePort(),
      }),
    });
    showRuntime(payload);
  }

  async function runtimeStopAll() {
    const payload = await request(
      `/operator-portal/api/portfolio/runtime/stop-all?approval_nonce=${encodeURIComponent(runtimeStopAllNonce)}`,
      { method: "POST" },
    );
    showRuntime(payload);
  }

  async function runtimeOpenAPI() {
    const identity = selectedRuntimeIdentity();
    const payload = await request("/operator-portal/api/portfolio/runtime/openapi", {
      method: "POST",
      body: JSON.stringify({
        app_id: identity.app_id,
        version_id: identity.version_id,
      }),
    });
    showRuntime(payload);
  }

  async function runtimeScenarios() {
    const identity = selectedRuntimeIdentity();
    const payload = await request("/operator-portal/api/portfolio/scenarios", {
      method: "POST",
      body: JSON.stringify({
        app_id: identity.app_id,
        version_id: identity.version_id,
        run_id: portfolioRuntimeRunId(),
        port: runtimePort(),
      }),
    });
    showRuntime(payload);
  }

  async function runtimeEvidence() {
    const payload = await request("/operator-portal/api/portfolio/evidence");
    showRuntime(payload);
  }

  async function refreshGuides() {
    const payload = await request("/portal/operator-guides");
    const guidePayload = payload.payload || {};
    const guides = Array.isArray(guidePayload.guides) ? guidePayload.guides : [];
    const taxonomy = guidePayload.status_taxonomy || {};
    setField("guides-status", guidePayload.status || payload.status);
    setField("guides-count", guides.length);
    setField("taxonomy-count", Object.keys(taxonomy).length);

    const list = document.getElementById("guide-list");
    if (list) {
      list.textContent = "";
      guides.forEach((guide) => {
        const item = document.createElement("li");
        item.textContent = `${guide.title}: ${guide.path}`;
        list.appendChild(item);
      });
    }
  }

  const actions = {
    "refresh-health": refreshHealth,
    "refresh-evidence": refreshEvidence,
    "refresh-download": refreshDownload,
    "export-download": exportDownload,
    "validation-dry-run": validationDryRun,
    "validation-run": validationRun,
    "latest-report": latestReport,
    "refresh-guides": refreshGuides,
    "refresh-run": refreshCurrentRun,
    "validate-requirements": validateRequirements,
    "submit-run": submitRun,
    "generate-plan": generatePlan,
    "approve-engineering": approveEngineering,
    "start-engineering": startEngineering,
    "cancel-run": cancelRun,
    "view-validation-report": viewValidationReport,
    "view-evidence": viewEvidence,
    "runtime-approve-start": () => runtimeApprove("start"),
    "runtime-start": runtimeStart,
    "runtime-openapi": runtimeOpenAPI,
    "runtime-scenarios": runtimeScenarios,
    "runtime-approve-restart": () => runtimeApprove("restart"),
    "runtime-restart": runtimeRestart,
    "runtime-approve-stop": () => runtimeApprove("stop"),
    "runtime-stop": runtimeStop,
    "runtime-approve-stop-all": () => runtimeApprove("stop_all"),
    "runtime-stop-all": runtimeStopAll,
    "runtime-evidence": runtimeEvidence,
  };

  function domainsForAction(action) {
    return actionLockDomains[action] || [action];
  }

  function conflictsWith(activeDomains, candidateDomains) {
    return candidateDomains.some((domain) => {
      if (domain === "runtime-global") {
        return activeDomains.some((active) => active.startsWith("runtime"));
      }
      if (activeDomains.includes("runtime-global") && domain.startsWith("runtime")) {
        return true;
      }
      return activeDomains.includes(domain);
    });
  }

  function updateActionLocks() {
    const activeDomains = Array.from(inFlightActions.values()).flat();
    document.querySelectorAll("[data-action]").forEach((button) => {
      const action = button.getAttribute("data-action") || "";
      const locked = conflictsWith(activeDomains, domainsForAction(action));
      button.disabled = locked;
      button.setAttribute("aria-disabled", locked ? "true" : "false");
    });
  }

  async function runCriticalAction(button, action, handler) {
    const domains = domainsForAction(action);
    const activeDomains = Array.from(inFlightActions.values()).flat();
    if (inFlightActions.has(action) || conflictsWith(activeDomains, domains)) {
      return;
    }
    const original = button.textContent || action;
    inFlightActions.set(action, domains);
    button.setAttribute("aria-busy", "true");
    button.innerHTML = `<span class="spinner" aria-hidden="true">...</span>${original}`;
    updateActionLocks();
    try {
      await handler();
    } finally {
      button.textContent = original;
      button.removeAttribute("aria-busy");
      inFlightActions.delete(action);
      updateActionLocks();
      updateControls(currentRunId ? { state: field("browser-run-state").textContent } : null);
    }
  }

  function bindActions() {
    document.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", async () => {
        const action = button.getAttribute("data-action");
        const handler = action ? actions[action] : undefined;
        if (!handler) {
          return;
        }
        try {
          await runCriticalAction(button, action, handler);
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          showError(message);
          showReport({ error: message });
        }
      });
    });
    const selector = runtimeSelector();
    if (selector) {
      selector.addEventListener("change", () => {
        const selected = selector.options[selector.selectedIndex];
        selectedRuntimeVersion =
          selected && selected.dataset.appId && selected.dataset.versionId
            ? { app_id: selected.dataset.appId, version_id: selected.dataset.versionId }
            : null;
        if (selectedRuntimeVersion) {
          window.localStorage.setItem("upi_app_factory_runtime_selection", selector.value);
          setField("runtime-selected-app", selectedRuntimeVersion.app_id);
          setField("runtime-selected-version", selectedRuntimeVersion.version_id);
        }
      });
    }
  }

  async function boot() {
    bindActions();
    updateControls(null);
    currentRunId = window.localStorage.getItem("upi_app_factory_current_run_id") || "";
    await Promise.all([
      refreshHealth(),
      refreshEvidence(),
      refreshDownload(),
      refreshGuides(),
      refreshPortfolioCatalogue(),
    ]);
    if (currentRunId) {
      await refreshCurrentRun();
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    boot().catch((error) => {
      showError(String(error));
      showReport({ error: String(error) });
    });
  });
})();
