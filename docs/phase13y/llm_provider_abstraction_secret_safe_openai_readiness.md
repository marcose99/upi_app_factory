# Phase 13Y — LLM Provider Abstraction and Secret-Safe OpenAI Readiness

Phase 13Y introduces a provider boundary for future LLM-backed agents without requiring a live OpenAI key.

The phase keeps validation deterministic and local while establishing:

- `LLMProviderPort`
- `LLMProviderConfig`
- `LLMCompletion`
- `LLMUsageMetadata`
- `LLMCallEvidence`
- `SecretReference`

## Governance intent

The factory must remain provider-portable and secret-safe. OpenAI is represented as configuration-only in this phase. No API key is required for validation, and no live LLM call is performed.

Secrets must never be committed, logged, placed into generated artifacts, or embedded in tests. A future live OpenAI mode must use environment variables or an external secret manager and must remain behind a policy gate.

## Evidence requirements

Every future LLM call must produce evidence for:

- provider
- model
- prompt hash
- response hash
- token usage
- cost estimate
- policy decision ID
- requirement IDs
- trace ID

This phase creates the schema and validates deterministic fallback so governance does not depend on external provider availability.
