# Phase 13V — Policy-Governed Self-Repairing Generation

Phase 13V strengthens the Phase 13U self-repair loop by making repair subject to
an explicit source-controlled policy file.

The runner remains deterministic and local in this phase. No OpenAI API key is
required. Future OpenAI-backed diagnosis may be enabled only by switching the
runtime mode and injecting secrets from the local environment or a secret manager;
secrets must never be committed to the repository.

Governance guarantees introduced here:

- source-controlled policy for generation and repair;
- explicit repair budget;
- diagnosis required before repair;
- policy decision required before repair;
- repair target restricted to generated application files;
- source, tests, docs, policies, and repository configuration are forbidden
  repair targets for the generated repair loop;
- validation must rerun after repair;
- audit evidence records policy, diagnosis, decision, repair, validation, and
  human release gate;
- external ecosystem boundaries remain mock/simulated only.
