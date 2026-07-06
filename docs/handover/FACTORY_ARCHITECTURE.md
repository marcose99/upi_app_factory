# Handover Factory Architecture

The factory consists of:

1. Governance layer
   - prompts
   - policies
   - validators
   - guardrails
   - audit scorecards

2. Agent-runtime foundation
   - agent registry
   - tool registry
   - runtime state
   - dry-run orchestrator
   - handoff ledger
   - tool execution ledger
   - runtime event ledger

3. Generated application workspace
   - disposable/recreatable generated application
   - local FastAPI app
   - tests
   - docs
   - evidence

4. Audit and self-correction layer
   - validation findings
   - governed correction decisions
   - self-correction ledgers
   - human approval boundaries
   - blocked categories

5. Portal layer
   - generation progress portal
   - agent runtime portal
   - self-correction portal

6. Handover layer
   - recipient quickstart
   - deployment guides
   - runbooks
   - release package manifest
   - troubleshooting guide
