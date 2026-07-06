# Phase 13O - Local Runnable Operator Demo Pack

Phase 13O packages the generated UPI dispute lifecycle application so another
operator can run and verify it locally with a lightweight command surface.

## Objective

Move from generated lifecycle code to a practical local handover surface:

- clear operator README;
- local health check;
- local dispute lifecycle demo;
- one-command operator demo;
- stdlib HTTP demo server;
- verifier script;
- governance audit and manifest.

## Lightweight runtime boundary

The pack remains local-first. It uses Python 3.10, the existing virtual
environment, filesystem evidence, and a stdlib HTTP server option. It does not
require Kubernetes, real payment rails, real bank integrations, NPCI-style
systems, RBI-style systems, upstream systems, or downstream systems.

## Agentic implementation

The pack is produced by a LangGraph `StateGraph` with these nodes:

- `generated_app_proof_agent`;
- `operator_pack_agent`;
- `smoke_verification_agent`;
- `governance_evidence_agent`.

## Operator command

After generation, run:

```bash
cd workspace/factory_generated/upi_dispute_resolution/operator_handoff/phase13o_local_runnable_pack
./run_operator_demo.sh
```
