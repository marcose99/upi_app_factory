# Phase 66 Problem Framing

Phase 66 adds a bounded rubric-alignment evidence layer to UPI App Factory
(`upi_app_factory`) and its generated application ID `upi_dispute_resolution`.
It does not rebuild the factory and does not alter the mock-only capstone.

## Users And Workflows

Realistic users are synthetic reviewers, product evaluators, dispute operations
analysts and governance reviewers. Their workflows are requirement intake,
mock dispute triage, evidence upload review, status tracking, ambiguity
escalation, safety refusal review and evaluator handoff.

Inputs are synthetic UPI dispute requirement cases, approved non-sensitive
repository documents, prompt variants, deterministic fixtures and optional live
OpenAI evaluator configuration. Outputs are JSONL, CSV, Markdown and manifest
evidence files with SHA-256 hashes, prompt hashes, retrieval metrics, safety
cases, memory experiments and validation results.

## Business Context

The business goal is to make the closed capstone easier for an evaluator to score
against a 100-point AI-engineering rubric while preserving stronger governance:
deterministic-first execution, local-first validation, mock payment boundaries
and fail-closed controls. Phase 66 evidence is evaluator-visible, reproducible
and explicit about `NOT_RUN` live measurements.

## Constraints And Assumptions

The repository must retain the product name UPI App Factory and the application
ID `upi_dispute_resolution`. External payment ecosystems remain mocked. Tests
must be hermetic and require no network or credentials. OpenAI live evaluation
is available only through `scripts/run_phase66_live_openai_evaluation.py` with
the explicit approval flag and `OPENAI_API_KEY`.

## Success Criteria

Success means every rubric subcriterion has an implementation path, evidence
path, reproduction command, measured result or `NOT_RUN`, and known limitation.
Offline evidence must be deterministic. Live LLM and embeddings results remain
`NOT_RUN` until the guarded live path executes.

## Failure Cases

Known failure cases include malformed structured output, provider failure,
timeout and retry exhaustion, prompt injection, PII or secret input, real payment
endpoint requests, destructive tool requests, approval bypass, unsupported
regulatory claims, low confidence and retrieval poisoning.

## Scope

In scope: prompts, fake and guarded live providers, schema validation, prompt
benchmarking, embeddings/RAG evidence, memory and feedback demos, monitoring,
safety evidence, validation and handoff packaging.

Out of scope: production payment integrations, bank/PSP/NPCI/RBI calls,
certification claims, repository release activity, deployment and unguarded
external API use.
