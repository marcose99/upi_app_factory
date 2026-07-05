# Phase 11A Agent Execution Policy — upi_dispute_resolution

## Purpose

Phase 11A creates the governed agentic code-generation harness. It does not yet
generate the final application implementation.

## Runtime policy

- Agents may read approved governance artifacts.
- Agents may propose file plans and patches.
- Agents may write only draft workspace artifacts after approval.
- Agents may not commit, merge, tag, push, or alter protected branches.
- Agents may not bypass deterministic validators.
- Agents may not introduce live bank, NPCI, RBI, PSP, customer, payment,
  ledger, notification, reconciliation, or ODR integrations.
- Agents may not use real customer data.
- Agents may not make certification, production-compliance, or legal-advice claims.

## Required labels

- MOCK_BOUNDARY
- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_DATA
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- TECHNOLOGY_SPECIFIC_BEST_PRACTICE_REQUIRED
- VERSION_SPECIFIC_REVIEW_REQUIRED
- HUMAN_APPROVAL_REQUIRED
- DETERMINISTIC_VALIDATION_REQUIRED

## Agentic principle

Agents generate proposals. Deterministic validators judge. Humans approve
protected changes. Git stores restore points.
