# Phase 0-1 Factory Builder Prompt

Use the existing factory_governance baseline. Generate only governance, evidence, domain foundation, risk tiers, policies, mock boundary policy, validation gates, task manifest, state machine, domain glossary, and test skeleton for `upi_dispute_case_management`.

Do not generate full business implementation yet.

Mandatory labels:
- MISSING_OFFICIAL_SOURCE for unsupported official UPI/NPCI/RBI claims.
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL for demonstration workflow.
- MOCK_BOUNDARY for all external integrations.
- SYNTHETIC_DATA for test data.

Return structured outputs with artifact paths, requirement IDs, policy IDs, evidence IDs, validation commands, risks, and limitations.
