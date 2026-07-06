# Audit-to-Remediation Runbook

Purpose: convert final audit findings into controlled remediation until quality objectives are met or the loop stops safely.

Flow:
1. Ingest final audit report.
2. Normalize findings.
3. Classify severity and remediation category.
4. Map each finding to quality objectives.
5. Build remediation plan.
6. Check remediation policy.
7. Auto-apply only allowed low-risk changes.
8. Request human approval for protected/high-risk changes.
9. Run validators and tests.
10. Compare before/after scores.
11. Update final report and HTML portal.
12. Continue until quality objectives are met or a stop condition occurs.

Required stop conditions:
- QUALITY_OBJECTIVES_MET
- HUMAN_APPROVAL_REQUIRED
- REMEDIATION_BUDGET_EXHAUSTED
- REGRESSION_DETECTED
- UNSAFE_REMEDIATION_BLOCKED
