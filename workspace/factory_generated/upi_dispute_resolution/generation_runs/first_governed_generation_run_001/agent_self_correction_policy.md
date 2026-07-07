# Governed Agent Self-Correction Policy

Every warning and error must be handled.

Required handling:
- classify severity and category
- decide auto-remediate, plan-only, human-approval-required, blocked, or no-change-needed
- ledger the decision
- ledger the correction attempt
- rerun validators after any applied correction
- stop on regression, blocked category, or human-approval boundary

Important:
- Agents may self-correct low-risk issues.
- Agents may not bypass governance.
- Agents may not weaken security, make live payment integrations, use real customer data,
  make false compliance claims, install dependencies, reset destructive paths, or commit/tag/push
  without the applicable approval boundary.
