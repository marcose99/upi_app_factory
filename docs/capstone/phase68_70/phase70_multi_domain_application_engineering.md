# Phase 70 Multi-Domain Application Engineering

Phase 70 extends the consolidated capstone with deterministic reusable capability profiles for six fictional dispute and exception domains. The workstream preserves the UPI App Factory posture: local-only, mock-only, fictional data, runtime LLM calls disabled by default, no real payment rails, and certification-ready-not-certified.

## Reused Platform Capabilities

- Phase 53 requirements compiler: `factory.application_engineering.requirements_compiler.compile_requirements` compiles the Phase 70 fixture set into a single traceable IR.
- Phase 56 deep composer: `factory.application_engineering.deep_composer.DeepApplicationComposer` is invoked during validation to prove the existing local-deep profile remains reusable.
- Phase 57 verification evidence contract: Phase 70 reference apps emit depth score, residual-risk, profile contract and test-obligation evidence shaped for the existing verification model.

## Portfolio Profiles

| Profile | Domain Coverage | Depth Score |
| --- | --- | ---: |
| `upi_failed_debit_no_credit` | UPI failed debit/no credit | 90 |
| `upi_reversal_refund_tracking` | UPI reversal or refund tracking | 88 |
| `upi_duplicate_debit` | UPI duplicate debit | 89 |
| `merchant_qr_acquirer_dispute` | Merchant QR/acquirer dispute | 87 |
| `fraud_mule_account_triage` | Fraud or mule-account triage | 91 |
| `card_authorization_chargeback` | Card authorization exception or chargeback | 89 |

Each profile declares stable requirement identifiers, domain states, guarded transitions, value objects, policies, events, commands, queries, ports, services, mock external boundaries, evidence artifacts, depth score and residual risks.

## Common Engineering Contract

Every profile must prove:

- idempotent command handling and replay of original outcomes;
- optimistic concurrency and stale-write rejection;
- deterministic event replay to a stable projection checksum;
- hash-chained audit records;
- outbox recording before mock publication;
- fictional local authorization and object-scope checks;
- PII redaction for account, card, phone and VPA-like values;
- strict safe input validation;
- unit, integration, contract, negative, resilience, security, performance-smoke and replay/audit obligations.

## Runtime Boundary

The validator generates representative reference applications under a temporary runtime root. Those generated files are not tracked and are not written under `workspace/`. The reference apps include a domain model, application contracts, security guards, mock infrastructure, focused contract test and evidence files for each profile.

## Validation

Run:

```sh
python scripts/validate_phase70_multi_domain_application_engineering.py
pytest tests/phase68_70/test_phase70_multi_domain_application_engineering.py
```

The validator fails closed if profile hashes drift from `factory_governance/phase68_70/phase70_profile_governance.json`, if requirements lineage is missing, if live boundary language is introduced, or if depth/test obligations fall below the Phase 70 contract.
