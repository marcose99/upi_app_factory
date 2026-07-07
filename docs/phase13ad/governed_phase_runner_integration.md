# Phase 13AD — Governed Self-Healing Integration into Phase Runners

## Purpose

Phase 13AC created the governed autonomous self-healing policy and classifier. Phase 13AD turns that capability into an integration point that every future phase runner can use.

This prevents the factory from returning to one-off repair scripts. The future pattern is:

1. Run gates.
2. Capture failure output.
3. Classify the failure with the Phase 13AC classifier.
4. Apply only allowed deterministic local repairs.
5. Re-run gates.
6. Record audit evidence.
7. Escalate unknown or high-risk failures to a human.
8. Keep merge, tag, and release approval human-gated.

## Governance improvement introduced

Phase 13AD adds a reusable governed phase-runner harness:

- `scripts/governed_phase_runner.py`
- `policies/phase13ad_governed_phase_runner_integration_policy.json`
- `scripts/validate_phase13ad_governed_phase_runner.py`
- `tests/test_phase13ad_governed_phase_runner.py`
- `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ad/governed_phase_runner_integration_audit.json`

This is a quality improvement because future automation now has a standard self-healing interface instead of ad hoc recovery logic.

## Human approval boundaries remain unchanged

The runner must escalate rather than auto-repair when a failure involves:

- live provider calls
- external system calls
- policy weakening
- security suppressions
- dependency changes
- evidence deletion
- regulatory/domain rule changes
- unknown failure patterns
- merge, tag, or release approval

## Expected future use

Future phase scripts should either call this runner directly or implement an equivalent policy-controlled gate with the same behavior and tests.
