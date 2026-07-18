# Repository governance

UPI App Factory uses pull-request-only changes to `main`, deterministic
quality gates, immutable action pins, least-privilege workflow
permissions, evidence archives, and explicit protected-action approval.

## Required checks

- Governance policy
- Ruff
- MyPy
- Focused tests
- Full regression

## Review model

`.github/CODEOWNERS` assigns `marcose99` as the current accountable owner.
This requests ownership review but does not manufacture independence.
A genuinely independent approval requires a second authorized reviewer.

## Protected decisions

Merge, ruleset activation, capstone tagging, release, deployment,
production-provider enablement, and certification claims require
explicit human authorization.

## Boundaries

The repository remains fictional, local-first, mock-safe,
certification-ready-not-certified, and does not perform production
payment processing or live provider calls.
