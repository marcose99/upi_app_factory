## Purpose

Describe the governed outcome and why the change is necessary.

## Governed scope

- [ ] Changed paths are explicitly listed.
- [ ] Unrelated refactoring is excluded.
- [ ] Generated/runtime noise is excluded.

## Validation evidence

- [ ] Focused tests passed.
- [ ] Full regression passed.
- [ ] Ruff passed.
- [ ] MyPy passed.
- [ ] Fresh-clone or recipient replay evidence is attached.

## Security and data handling

- [ ] No secrets or real payment credentials are present.
- [ ] Real payment/provider calls remain disabled.
- [ ] Mock/local boundaries remain enforced.
- [ ] Actions are pinned to full commit SHAs.

## Human decisions

Identify protected decisions such as merge, ruleset activation,
tagging, release, deployment, certification, or exception approval.

## Residual risks

State remaining limitations and explicitly distinguish
certification-ready evidence from actual certification.
