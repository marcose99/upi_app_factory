# Release and Rollback Runbook

Release requires:
- clean working tree;
- all validators pass;
- all quality objectives met or accepted by human reviewer;
- final audit report generated;
- human-validator portal updated;
- no forbidden claims;
- tag created from integrated main branch.

Rollback requires:
- identify last known good tag;
- capture failed state and logs;
- revert or reset according to branch policy;
- re-run validators;
- document residual risk and lessons learned.
