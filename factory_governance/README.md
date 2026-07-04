# Governed Agentic Software Factory — Final Reusable Artifact Pack

Status: FINAL BASELINE v1.0  
Purpose: Reusable production-grade starter pack for creating governed AI-agent software factories.

This pack deliberately separates the factory into:

1. a lean always-loaded system prompt,
2. project-specific charter and requirements templates,
3. role-specific agent prompts,
4. machine-checkable YAML/JSON control artifacts,
5. debugging, regeneration, security, observability, and release playbooks.

The design principle is simple:

> The LLM proposes. The orchestrator controls. Policies decide. Tools act through approved gateways. Tests and evidence determine readiness. Humans approve high-risk actions.

## How to use this pack

1. Copy this folder into the root of a new project as `factory_governance/`.
2. Fill `01_PROJECT_CHARTER_TEMPLATE.md` with actual project facts.
3. Load `00_SYSTEM_PROMPT.md` as the always-active system prompt.
4. Load only the relevant agent prompt section from `03_AGENT_ROLE_PROMPTS.md` for each agent execution.
5. Treat YAML/JSON files as the source for your orchestrator, CI checks, policy checks, and evidence collection.
6. Run `python validate_factory_pack.py` to perform a basic pack integrity check.

## What this pack is

- A high-standard reusable governance baseline.
- A production-oriented architecture for agentic software delivery.
- A safe default for regulated, audited, or business-critical domains.
- A starting point for turning agent behavior into enforceable controls.

## What this pack is not

- It is not legal, regulatory, financial, medical, or security certification.
- It is not a substitute for organization-specific risk approval.
- It does not guarantee zero hallucination by prompt alone.
- It does not remove the need for tests, review, audit, and human accountability.

## Artifact index

| File | Purpose |
|---|---|
| `00_SYSTEM_PROMPT.md` | Lean always-loaded system constitution |
| `01_PROJECT_CHARTER_TEMPLATE.md` | Project-specific facts and constraints |
| `02_FACTORY_OPERATING_MANUAL.md` | Full factory lifecycle |
| `03_AGENT_ROLE_PROMPTS.md` | Role-specific bounded agent prompts |
| `04_RISK_TIERS.yaml` | Risk classification and approval levels |
| `05_POLICY_REGISTRY.yaml` | Starter machine-readable policies |
| `06_VALIDATION_GATES.yaml` | Validation gate definitions |
| `07_TASK_MANIFEST_SCHEMA.json` | Task manifest schema |
| `08_ARTIFACT_MANIFEST_SCHEMA.json` | Artifact manifest schema |
| `09_AUDIT_EVENT_SCHEMA.json` | Audit event schema |
| `10_DEBUG_CASE_SCHEMA.json` | Debug case schema |
| `11_REGENERATION_GUIDE.md` | Repeatable rebuild/regeneration process |
| `12_DEBUGGING_PLAYBOOK.md` | Needle-from-haystack forensic debugging guide |
| `13_RELEASE_READINESS_CHECKLIST.md` | Release/demo evidence checklist |
| `14_SECURITY_AND_RED_TEAM_PLAYBOOK.md` | LLM/application security and adversarial testing |
| `15_OBSERVABILITY_STANDARD.md` | Logs, traces, metrics, audit, and IDs |
| `16_EVIDENCE_LEDGER_TEMPLATE.csv` | Evidence ledger starter |
| `17_GOLDEN_REGRESSION_SUITE_TEMPLATE.md` | Golden test and hallucination regression template |
| `18_HUMAN_APPROVAL_POLICY.md` | Human approval gates and decision records |
| `19_MATURITY_MODEL.md` | L0-L6 maturity model |
| `20_FINAL_REVIEWER_CHECKLIST.md` | Review council checklist |
| `21_REFERENCE_BASE.md` | Official reference anchors |
| `factory_pack_manifest.json` | File hashes and manifest |
| `validate_factory_pack.py` | Basic integrity validator |

## Recommended repository location

```text
<project-root>/
  factory_governance/
    00_SYSTEM_PROMPT.md
    01_PROJECT_CHARTER_TEMPLATE.md
    ...
  requirements/
  architecture/
  design/
  task_manifests/
  audit/
  evidence/
  validation_reports/
  generated_artifacts/
```

## Final operating rule

If there is no evidence, say so. If there is no validation, do not claim success. If an action is risky, require approval. If a result is mocked, label it mocked. If the system cannot be debugged, it is not production-ready.
