(function () {
  "use strict";

  const fields = new Map();

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
          showReport({ error: error instanceof Error ? error.message : String(error) });
        } finally {
          button.removeAttribute("aria-busy");
        }
      });
    });
  }

  async function boot() {
    bindActions();
    await Promise.all([refreshHealth(), refreshEvidence(), refreshDownload(), refreshGuides()]);
  }

  window.addEventListener("DOMContentLoaded", () => {
    boot().catch((error) => showReport({ error: String(error) }));
  });
})();
