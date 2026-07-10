# Phase 46G — Governed multi-phase campaign and bounded self-repair

Phase 46G installs a repository-native campaign controller above the existing
single-phase lifecycle engine. A campaign accepts one approval set, sequences
active phase manifests, records durable campaign state, resumes after
interruption, and stops fail-closed when no approved repair is available.

The first automatic repair is deliberately narrow: Ruff safe fixes may be
applied only when every diagnostic belongs to a manifest-approved Python
candidate and Ruff marks every finding as safely fixable. The lifecycle is then
rolled back to `IMPLEMENTED`, stale evidence is invalidated, and all affected
gates rerun.

The bundled identity-modernization campaign executes Phase 46H, Phase 46I, and
Phase 46J. It does not rename the checkout or remote repository, remove legacy
aliases, create a tag, perform a release, call a live provider, or claim formal
certification.

## Integration hardening

Future phase manifests remain `DRAFT` in the repository and are copied into
campaign state with `ACTIVE` status only immediately before their governed
execution. This prevents future-phase declarations from changing the current
full-regression contract.

Repair dispatch classifies the failed gate before selecting an automatic
repair. Only candidate-scoped Ruff safe fixes are automatic. Pytest, MyPy,
policy, candidate, and secret-scan failures fail closed with exact evidence.

Future path-neutral payloads prohibit arbitrary absolute paths and contain no
machine-specific checkout literal.

Every campaign phase provisions the hash-verified ignored lifecycle evidence
needed by the complete regression suite before implementation and validation.

