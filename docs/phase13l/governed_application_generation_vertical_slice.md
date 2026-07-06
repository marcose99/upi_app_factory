# Phase 13L - Governed Application Generation Vertical Slice

Phase 13L moves the factory from release-handoff and replay verification into
visible governed application generation.

## Scope

The first vertical slice is dispute case intake for the primary local UPI
dispute-resolution application.

Generated app responsibilities:

- validate a UPI dispute-intake request;
- create a local dispute case;
- expose a small API facade;
- keep an in-memory repository for the generated slice;
- include generated verification checks and smoke execution without polluting repository-level pytest discovery;
- record deterministic generation evidence.

External ecosystem responsibilities:

- bank-directory calls are mock/simulated;
- NPCI-style reference reservation is mock/simulated;
- RBI-style, rail, bank, upstream, and downstream integrations are not real
  integrations in this phase.

## Package isolation repair

The generated application package is named
`phase13l_dispute_case_intake_app`, not `app`. This avoids collision with the
factory repository's existing top-level `app` package when pytest runs from the
repo root.

## Governance rule

The primary generated UPI application slice should be engineered as a real,
locally runnable application component. External ecosystem applications,
payment rails, banks, NPCI/RBI-style interfaces, upstream systems, and
downstream integrations remain simulated boundaries until explicitly promoted
through later governance.
