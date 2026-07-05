# Phase 11A.1 Prompt — Essential Agentic Harness Hardening

Add the missing operational controls required before real governed agents
generate application code.

Required controls:

- autonomy levels
- fail-closed tool permission matrix
- human approval ledger schema
- checkpoint and replay policy
- prompt-injection and untrusted-input policy
- secret and environment guard policy
- model/provider/budget policy
- repair-loop limit policy
- generated-code acceptance contract
- agent evaluation rubric
- Phase 11B go/no-go gate

Non-negotiables:

- Agents must not commit, merge, tag, push, or release.
- Agents must not bypass deterministic validators.
- Agents must not access secrets or real customer data.
- Unknown tools and paths must FAIL_CLOSED.
- Human approval is required for protected writes.
- Deterministic validation is required before generated code is accepted.
