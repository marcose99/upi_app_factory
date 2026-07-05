# Governed Agent Prompt Quality Guide

This guide defines how prompts should be written for FactoryFromNothing / `upi_dispute_resolution_factory` agents.

## Purpose

The project is moving from deterministic scripts toward governed agentic factory runs. The prompts must therefore make agents useful without allowing them to invent facts, hide uncertainty, or bypass validation.

## Prompt quality principles

1. **Ground every answer.** Use only supplied repository files, run evidence, terminal output, uploaded artifacts, and explicit user instructions.
2. **Do not invent official sources.** If NPCI, RBI, bank, PSP, switch, or regulatory evidence is not supplied, preserve `MISSING_OFFICIAL_SOURCE`.
3. **Preserve mock boundaries.** Mock systems must remain clearly marked as `MOCK_BOUNDARY` and `SYNTHETIC_DATA`.
4. **Trace every artifact.** Generated artifacts should link to requirement IDs, task IDs, policy IDs, and evidence references.
5. **Make debugging easy.** Prompts should demand file paths, commands, expected good output, and first-failure analysis.
6. **Prefer beginner readability.** Ask for clear names, small functions, explicit validation, simple control flow, and helpful errors.
7. **Separate facts from assumptions.** Never present assumptions as validated evidence.
8. **Validate before release.** Do not recommend merge, tag, or push unless validation output supports it.

## Required prompt structure

Each agent prompt should contain:

- Agent identity
- Primary goal
- Grounding contract
- Responsibilities
- Anti-hallucination rules
- Required traceability fields
- Beginner-readable output rules
- Expected outputs
- Refusal or escalation rule

## Agent prompt inventory

| Agent ID | Agent Name | Primary Goal |
|---|---|---|
| `requirement_agent` | Requirement Agent | Convert user or stakeholder intent into clear, testable, traceable requirements. |
| `domain_agent` | Domain Agent | Explain the UPI dispute-resolution domain using only supplied evidence and explicit synthetic labels. |
| `architect_agent` | Architect Agent | Design a lightweight but production-disciplined architecture with clear trade-offs. |
| `planner_agent` | Planner Agent | Break work into safe, ordered, reviewable, and testable implementation steps. |
| `developer_agent` | Developer Agent | Generate beginner-readable, deterministic, testable Python code that follows approved design. |
| `test_agent` | Test Agent | Prove behavior through deterministic tests, negative cases, and validation commands. |
| `security_agent` | Security Agent | Identify security risks, unsafe defaults, secret exposure, and dependency risks within the current project scope. |
| `governance_agent` | Governance Agent | Ensure policy, honesty labels, mock boundaries, and evidence-ledger expectations are enforced. |
| `evidence_agent` | Evidence Agent | Collect, hash, reference, and preserve evidence for every governed factory run. |
| `reviewer_agent` | Reviewer Agent | Review generated work for correctness, readability, debugability, governance, and release readiness. |
| `release_agent` | Release Agent | Prepare branch merge, restore tag, release notes, and rollback guidance only after all gates pass. |
| `operations_agent` | Operations Agent | Make local run, validation, troubleshooting, and recovery steps simple and safe. |
| `regeneration_agent` | Regeneration Agent | Regenerate mock dispute app artifacts deterministically and record evidence of the run. |
| `traceability_agent` | Traceability Agent | Map every generated artifact to requirement, task, policy, and evidence references. |
| `validation_agent` | Validation Agent | Run and summarize deterministic validation gates in a way reviewers can trust. |

## Strong prompt statements

Use these statements when asking an agent to work:

```text
Use only supplied project evidence. Do not invent official sources, command results, hashes, validation status, policies, or production integrations.
```

```text
For every artifact, include requirement IDs, task IDs, policy IDs, evidence references, honesty labels, known limitations, and validation commands.
```

```text
Generate beginner-readable, debug-friendly Python 3.10 code with clear names, small functions, explicit validation, helpful errors, and simple control flow.
```

```text
Diagnose terminal output by identifying the first failing command, first meaningful error, likely root cause, safest next command, and expected good output.
```

```text
If evidence is missing, say what is missing and preserve the correct honesty label instead of guessing.
```

## Validation

Run:

```bash
make validate-agent-prompts
```

Expected result:

```json
{
  "errors": [],
  "passed": true
}
```


## Per-agent anti-hallucination minimum

Every individual agent prompt must explicitly contain these terms so reviewers and validators can verify the control without opening the common contract:

- `MISSING_OFFICIAL_SOURCE`
- `SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL`
- `MOCK_BOUNDARY`
- `SYNTHETIC_DATA`
- `requirement_ids`
- `task_ids`
- `policy_ids`
- `evidence_refs`
- `honesty_labels`
- `validation_commands`
- `beginner-readable`
- `debug`
- `If evidence is missing`
- `Do not hallucinate`
