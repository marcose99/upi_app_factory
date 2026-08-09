# Contributing

Thank you for improving UPI App Factory.

## Scope

Contributions should preserve the project's lightweight, local-first, mock-safe and evidence-driven engineering model. Do not introduce real payment calls, real customer data, production credentials, or weaker safety/governance defaults.

## Workflow

1. Fork or create a feature branch from the current `main`.
2. Keep the change narrowly scoped and explain the engineering reason.
3. Add or update tests and documentation when behavior changes.
4. Run the relevant focused checks, then:
   ```bash
   python -m ruff check .
   python -m mypy .
   python -m pytest -q
   ```
5. Open a pull request using the repository template.
6. Treat Governed CI as revision-specific evidence; do not reuse a green result from another commit.

## Engineering expectations

- Preserve deterministic and clean-room reproducibility.
- Fail closed rather than weakening a test, security control or governance boundary.
- Keep generated-application specifics in application profiles when the rule is not generic to the UPI factory.
- Do not commit secrets, `.env` credentials, real PII, payment credentials or private keys.
- Do not force-push protected delivery history merely to make it cosmetically cleaner.

See `docs/DOCUMENTATION_INDEX.md` and `docs/governance/RELEASE_GOVERNANCE.md`.
