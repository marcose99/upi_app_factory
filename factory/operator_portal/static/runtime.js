async function loadRuntimeStatus(runId) {
  const response = await fetch(`/operator-portal/api/runtime/runs/${encodeURIComponent(runId)}/status`);
  if (!response.ok) {
    throw new Error("Runtime status unavailable");
  }
  return response.json();
}

window.upiAppFactoryRuntime = { loadRuntimeStatus };
