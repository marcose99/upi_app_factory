# Phase 66 Architecture

Phase 66 is implemented under `src/upi_factory/rubric_alignment/`.

Core modules:

- `models.py`: typed contracts for providers, embeddings, prompt variants,
  requirement analyses, retrieval chunks, tool routing, memory and feedback.
- `prompts.py`: three materially different prompt variants with version and
  SHA-256 recording.
- `providers.py`: deterministic fake provider, retry wrapper and guarded OpenAI
  Responses API provider using structured outputs.
- `schema.py`: strict local schema validation before evidence is accepted.
- `safety.py`: synthetic-data, PII, secret, approval-bypass and mock-boundary
  enforcement.
- `retrieval.py`: deterministic corpus loading, stable chunks, fake embeddings
  for tests, optional OpenAI embeddings for the guarded live path, persisted
  JSONL vector index and cosine top-k search.
- `memory.py`: session, workflow and evidence memory scopes with reset,
  retention metadata, expiry, cross-run isolation and sensitive-memory rejection.
- `benchmark.py`: deterministic offline benchmark and evidence generation.
- `live.py`: guarded live OpenAI evaluation gate.
- `validation.py` and `handoff.py`: evaluator validation and portable handoff.

The OpenAI live path is intentionally separate from offline evaluation. It fails
closed unless `--approve-live-openai-evaluation` and `OPENAI_API_KEY` are both
present. The implementation is aligned to the official OpenAI references for
Responses API, structured outputs, embeddings and safety best practices:

- Responses API: https://developers.openai.com/api/reference/resources/responses/methods/create
- Structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- Embeddings: https://developers.openai.com/api/docs/guides/embeddings
- Safety best practices: https://developers.openai.com/api/docs/guides/safety-best-practices
- Codex non-interactive mode: https://learn.chatgpt.com/docs/non-interactive-mode

The architecture does not call real banks, PSPs, NPCI, RBI, payment rails or
production services. External payment behavior remains mocked or simulated.
