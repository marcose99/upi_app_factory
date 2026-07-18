# Phase 68 Recipient Replay

Phase 68 provides a one-command offline recipient replay for UPI App Factory.
It uses only repository-tracked fixtures and deterministic Python standard-library
logic.

Run:

```bash
python scripts/run_phase68_recipient_replay.py
python scripts/validate_phase68_reproducible_evaluator_recipient.py
```

The replay demonstrates requirements intake, architecture and governance
explanation, generated-application inspection, safety scenarios, benchmark
summary, evidence verification and application download handoff. The generated
handoff bundle is checksummed and accompanied by a content manifest.

Boundaries:

- Fictional data only.
- Certification-ready-not-certified.
- No official certification claim.
- No production readiness claim.
- No original ignored workspace, credentials, network, Docker, OpenAI access or
  live provider access.
- Real payment, bank, PSP, NPCI, RBI and card-network calls are disabled.

The independent verifier fails closed for manifest tampering, payload tampering,
missing artifacts, path traversal, symlinks, unsupported production or
certification claims and mock-boundary violations.

