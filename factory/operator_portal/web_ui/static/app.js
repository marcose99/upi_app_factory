(function () {
  "use strict";

  const fields = new Map();
  let currentRunId = "";
  let pollTimer = 0;

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
    setField("browser-run-id", currentRunId || "Not created");
    setField("browser-run-state", run.state);
    setField("browser-run-sha", run.requirements_sha256);
    setField("browser-approval-state", run.approval ? "approved" : "required");
    setField("browser-updated-at", run.updated_at_utc);
    setField("browser-final-decision", run.final_decision || "Waiting");
    showRunEvents(run.events || []);
    updateDownloadLinks(run);
    updateControls(run);
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
  };

  function bindActions() {
    document.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", async () => {
        const action = button.getAttribute("data-action");
        const handler = action ? actions[action] : undefined;
        if (!handler) {
          return;
        }
        button.setAttribute("aria-busy", "true");
        try {
          await handler();
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          showError(message);
          showReport({ error: message });
        } finally {
          button.removeAttribute("aria-busy");
        }
      });
    });
  }

  async function boot() {
    bindActions();
    updateControls(null);
    await Promise.all([refreshHealth(), refreshEvidence(), refreshDownload(), refreshGuides()]);
  }

  window.addEventListener("DOMContentLoaded", () => {
    boot().catch((error) => {
      showError(String(error));
      showReport({ error: String(error) });
    });
  });
})();
