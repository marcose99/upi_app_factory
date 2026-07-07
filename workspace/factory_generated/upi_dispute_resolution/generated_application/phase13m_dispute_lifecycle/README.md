# Phase 13M Dispute Lifecycle Slice

This generated component is a local runnable UPI dispute-resolution lifecycle
slice. It extends intake into lifecycle status transitions, evidence validation,
mock investigation response handling, resolution decisioning, and audit trail
creation.

Agent orchestration is performed by a real LangGraph StateGraph. The graph is
local-first and deterministic in this phase, but it is a true agentic graph with
state, nodes, directed edges, and a conditional self-correction route.

External ecosystem boundaries are deliberately mock/simulated only. Banks,
NPCI-style, RBI-style, payment rail, upstream, and downstream interfaces are not
real integrations in this slice.

## Run locally

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application/phase13m_dispute_lifecycle
python3 scripts/run_demo.py
PYTHONPATH=. python3 -m pytest -q checks/dispute_lifecycle_checks.py
```
