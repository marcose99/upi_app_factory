# Phase 43 Reviewer Pack

## What The Factory Does

FactoryFromNothing assembles governed software-factory artifacts and a locally
runnable generated UPI dispute-resolution application. The generated application
supports synthetic dispute intake, mock ecosystem checks, local persistence,
audit events, and reviewer-facing validation evidence.

## How To Run It

From the repository root, use the one-command reviewer surface:

```bash
make phase43-demo-reviewer-pack
```

The command prints exact staged commands because fully automating the visible
demo would require starting a long-running local web server. For bounded
mock-only checks that do not start a server:

```bash
python scripts/run_phase43_one_command_demo_reviewer_pack.py --run-safe-checks
```

## What Evidence To Inspect

- `policies/phase43_one_command_demo_reviewer_pack_policy.json`
- `prompts/phase43/one_command_demo_reviewer_pack_prompt.md`
- `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/`
- `scripts/validate_phase43_one_command_demo_reviewer_pack.py`
- `tests/test_phase43_one_command_demo_reviewer_pack.py`
- Phase 34 validation runner report and generated app local run-pack evidence

## What Is Intentionally Mocked

UPI rails, NPCI/RBI interfaces, banks, PSPs, payment rails, ODR systems,
notifications, customer systems, upstream/downstream integrations, and
third-party services remain mocked or simulated.

## Certification Boundary

The posture is `certification_ready_not_certified`. This pack does not claim
official certification, official approval, live payment capability, legal
sufficiency, or broad production readiness.

## Known Limitations

The demo is local and synthetic. It does not connect to external ecosystems,
does not create real credentials, does not deploy, and does not replace formal
compliance, security, performance, or certification review.
