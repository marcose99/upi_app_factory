# Phase 13AC — Governed Autonomous Self-Healing Policy and Repair Classifier

## Purpose

Phase 13AC makes governed autonomous self-healing a reusable factory capability.

The factory should not rely on manual one-error-at-a-time repair when it can safely classify a known local failure, apply a deterministic repair, and re-run all gates. At the same time, the factory must not become uncontrolled automation.

## Operating model

The default execution mode is:

1. Run validation gates.
2. Classify failures.
3. Apply only approved deterministic local repairs.
4. Re-run gates.
5. Commit repair evidence.
6. Stop and escalate if the failure is unknown or high risk.
7. Keep final release approval human-gated.

## Allowed autonomous repairs

- MyPy active-source scope normalization.
- MyPy package-boundary stabilization.
- Ruff safe auto-fix with re-validation.
- Deterministic local artifact regeneration.
- Known-safe validator/schema alignment when policy-controlled.

## Blocked autonomous repairs

- Live LLM/provider calls.
- External payment, banking, NPCI/RBI, or ecosystem calls.
- Policy weakening.
- Test or quality-gate bypassing.
- Security suppressions.
- Dependency changes.
- Data/evidence deletion.
- Regulatory/domain rule changes.
- Merge, tag, or release approval without human gate.
- Any unknown failure pattern.

## Human approval boundaries

Human approval remains required for:

- Merge/tag/release decisions.
- Live provider activation.
- External calls.
- Dependency/supply-chain changes.
- Security exceptions.
- Policy weakening.
- Regulatory/domain-rule changes.
- Unknown or ambiguous repair patterns.

## Phase 13AC decision

Phase 13AC introduces the policy, classifier, evidence audit artifact, documentation, and tests required to make governed autonomous self-healing repeatable for future milestones.

The self-healing classifier is intentionally conservative: it returns `ESCALATE_TO_HUMAN` for unknown or high-risk categories.
