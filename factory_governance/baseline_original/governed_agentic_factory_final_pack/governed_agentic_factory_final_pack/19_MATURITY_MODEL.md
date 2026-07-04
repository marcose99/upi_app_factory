# 19 — Maturity Model

Status: FINAL BASELINE v1.0

## Purpose

Prevent false maturity claims. A factory must state its current level honestly.

## Levels

| Level | Name | Description | Minimum evidence |
|---|---|---|---|
| L0 | Concept only | Idea, prompt, or rough design | concept note |
| L1 | Local demo | Runs locally with limited validation | run instructions, demo validation |
| L2 | Governed demo | Requirements, policies, mock boundaries, and validation exist | charter, policies, tests, mock disclosure |
| L3 | Repeatable regeneration | Factory can regenerate artifacts with manifests and diffs | regeneration manifest, artifact manifest, validation report |
| L4 | Pre-production candidate | Serious quality gates and security review passed in non-production context | full test suite, security review, observability, known limitations |
| L5 | Production candidate | Release controls, approvals, rollback, monitoring, and operational readiness exist | release pack, approvals, runbooks, rollback, evidence completeness |
| L6 | Audited production operation | Operating in production with ongoing audit, monitoring, incident handling, and change control | operational audit logs, incident process, periodic review, compliance evidence where applicable |

## Naming rules

- Do not call L1/L2 “production-ready.”
- Do not call mock integrations “real integrations.”
- Do not call validation “certification.”
- Do not call evidence “compliance proof” unless compliance requirements and controls are explicitly mapped and reviewed.

## Promotion criteria

Promotion from one level to the next requires:

- passing required validation gates,
- no open blockers,
- complete evidence pack for that level,
- known limitations documented,
- approval where required.
